import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { AssetPage, AssetRecord, mapAssetDto, mapAssetPage, parseAssetDto, parsePageDto, uuidPattern } from './assetDtos';

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

// A deliberately read-only F1 interface. The wider mock workflow interface cannot honestly model this API yet.
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
}
