import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { AssetPage, AssetRecord, mapAssetDto, mapAssetPage, parseAssetDto, parsePageDto, uuidPattern } from './assetDtos';
import { AcquisitionRecord, CategoryRecord, ReferenceKind, ReferenceRecord, mapAcquisitionDto, mapCategoryDto, mapReferenceDto, parseAcquisitionDto, parseCategoryDto, parseReferenceDto } from './assetDtos';
import { CreateAcquisitionDto, CreateAssetDto } from './acquisitionForm';

export interface AssetQuery {
  page: number; pageSize: number; search: string; status: string;
  category: string; department: string; location: string; ordering: string;
}
export const defaultAssetQuery: AssetQuery = {
  page: 1, pageSize: 25, search: '', status: '', category: '', department: '', location: '', ordering: 'tag',
};
const orderingFields: Record<string, string> = {
  tag: 'asset_tag', name: 'name', status: 'status', acquisitionDate: 'acquisition_date',
  purchaseCost: 'purchase_cost', bookValue: 'current_book_value', createdAt: 'created_at',
};
export function assetQueryParams(query: AssetQuery) {
  const descending = query.ordering.startsWith('-');
  const field = orderingFields[descending ? query.ordering.slice(1) : query.ordering];
  if (!field || !Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.pageSize) || query.pageSize < 1) {
    throw new ApiError('validation', 'Invalid asset pagination or ordering.');
  }
  return { page: query.page, page_size: Math.min(100, query.pageSize), search: query.search,
    status: query.status, category: query.category, department: query.department, location: query.location,
    ordering: `${descending ? '-' : ''}${field}` };
}

// This interface exposes only asset reads; the Django repository's write methods remain separate from the mock contract.
export interface AssetReader {
  getAssets(query: AssetQuery, signal?: AbortSignal): Promise<AssetPage>;
  getAssetById(id: string, signal?: AbortSignal): Promise<AssetRecord>;
}
export class DjangoAssetRepository implements AssetReader {
  constructor(private readonly api: ApiClient) {}
  async getAssets(query: AssetQuery, signal?: AbortSignal): Promise<AssetPage> {
    const params = assetQueryParams(query);
    const body = await this.api.request('/assets/', { query: params, signal });
    return mapAssetPage(parsePageDto(body, parseAssetDto), query.page, params.page_size);
  }
  async getAssetById(id: string, signal?: AbortSignal): Promise<AssetRecord> {
    if (!uuidPattern.test(id)) throw new ApiError('not-found', 'The requested asset ID is not a valid UUID.', 404);
    return mapAssetDto(parseAssetDto(await this.api.request(`/assets/${id}/`, { signal })));
  }

  async getAssetByTag(tag: string): Promise<AssetRecord | null> {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(tag)) throw new ApiError('validation', 'Enter a valid asset tag.');
    try { return mapAssetDto(parseAssetDto(await this.api.request(`/assets/by-tag/${encodeURIComponent(tag)}/`))); }
    catch (error) { if (error instanceof ApiError && error.kind === 'not-found') return null; throw error; }
  }

  private async allPages<T extends { id: string }>(path: string, parse: (row: unknown) => T, signal?: AbortSignal): Promise<T[]> {
    const rows: T[] = [], seen = new Set<string>();
    let expectedCount: number | undefined;
    for (let page = 1; ; page++) {
      const dto = parsePageDto(await this.api.request(path, { query: { page, page_size: 100 }, signal }), parse);
      if (expectedCount === undefined) expectedCount = dto.count;
      if (dto.count !== expectedCount || rows.length + dto.results.length > dto.count || (dto.next && page * 100 >= dto.count)) {
        throw new ApiError('contract', 'Reference pagination changed unexpectedly. Please reload.');
      }
      if (!dto.results.length && dto.next) throw new ApiError('contract', 'Reference pagination did not advance. Please reload.');
      for (const row of dto.results) {
        if (seen.has(row.id)) throw new ApiError('contract', 'Reference data changed while loading. Please reload.');
        seen.add(row.id); rows.push(row);
      }
      if (!dto.next) {
        if (rows.length !== dto.count) throw new ApiError('contract', 'Reference data is incomplete. Please reload.');
        return rows;
      }
    }
  }
  getCategories(signal?: AbortSignal): Promise<CategoryRecord[]> {
    return this.allPages('/assets/categories/', row => mapCategoryDto(parseCategoryDto(row)), signal);
  }
  getReferences(kind: ReferenceKind, signal?: AbortSignal): Promise<ReferenceRecord[]> {
    if (kind === 'categories') return this.getCategories(signal);
    return this.allPages(kind === 'departments' ? '/departments/' : '/locations/', row => mapReferenceDto(parseReferenceDto(row)), signal);
  }

  async createAsset(dto: CreateAssetDto): Promise<AssetRecord> {
    return mapAssetDto(parseAssetDto(await this.api.request('/assets/', { method: 'POST', body: dto })));
  }
  async getAcquisitions(query: { page: number; search?: string; asset?: string; status?: string }, signal?: AbortSignal) {
    const dto = parsePageDto(await this.api.request('/assets/acquisitions/', { query: { ...query, page_size: 25 }, signal }), parseAcquisitionDto);
    const data = dto.results.map(mapAcquisitionDto);
    if (query.asset && (dto.count > 1 || data.some(row => row.assetId !== query.asset))) {
      throw new ApiError('contract', 'The acquisition response did not match the requested asset.');
    }
    return { data, total: dto.count, page: query.page,
      totalPages: Math.max(1, Math.ceil(dto.count / 25)), hasNext: !!dto.next, hasPrevious: !!dto.previous };
  }
  async getAcquisitionForAsset(assetId: string, signal?: AbortSignal): Promise<AcquisitionRecord | null> {
    if (!uuidPattern.test(assetId)) throw new ApiError('validation', 'Invalid asset UUID.');
    const page = await this.getAcquisitions({ page: 1, asset: assetId }, signal);
    if (page.total > 1 || (page.data[0] && page.data[0].assetId !== assetId)) throw new ApiError('contract', 'The acquisition response did not match the asset.');
    return page.data[0] ?? null;
  }
  async createAcquisition(dto: CreateAcquisitionDto): Promise<AcquisitionRecord> {
    const row = mapAcquisitionDto(parseAcquisitionDto(await this.api.request('/assets/acquisitions/', { method: 'POST', body: dto })));
    if (row.assetId !== dto.asset_id) throw new ApiError('contract', 'The acquisition response did not match the asset.');
    return row;
  }
  async updateAcquisition(id: string, dto: CreateAcquisitionDto): Promise<AcquisitionRecord> {
    if (!uuidPattern.test(id)) throw new ApiError('validation', 'Invalid acquisition UUID.');
    const { asset_id, ...body } = dto; // Asset association is immutable on update.
    const row = mapAcquisitionDto(parseAcquisitionDto(await this.api.request(`/assets/acquisitions/${id}/`, { method: 'PATCH', body })));
    if (row.id !== id || row.assetId !== asset_id) throw new ApiError('contract', 'The acquisition response did not match the asset.');
    return row;
  }
  async capitalizeAcquisition(id: string): Promise<AcquisitionRecord> {
    if (!uuidPattern.test(id)) throw new ApiError('validation', 'Invalid acquisition UUID.');
    const row = mapAcquisitionDto(parseAcquisitionDto(await this.api.request(`/assets/acquisitions/${id}/capitalize/`, { method: 'POST' })));
    if (row.id !== id || row.status !== 'CAPITALIZED') throw new ApiError('contract', 'Capitalization returned an unexpected response. Reconcile before continuing.');
    return row;
  }
}
