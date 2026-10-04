import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { DepreciationEntryRecord, DepreciationScheduleRecord, AccountingPeriodRecord, mapAccountingPeriodDto, mapDepreciationEntryDto, mapDepreciationScheduleDto, parseAccountingPeriodDto, parseDepreciationEntryDto, parseDepreciationPageDto, parseDepreciationScheduleDto } from './depreciationDtos';

export class DjangoDepreciationRepository {
  constructor(private readonly api: ApiClient) {}
  private async allPages<T>(path: string, parse: (row: unknown) => T, query: Record<string, string>, signal?: AbortSignal): Promise<T[]> {
    const result: T[] = []; const seen = new Set<string>(); let count: number | undefined;
    for (let page = 1; ; page++) {
      const dto = parseDepreciationPageDto(await this.api.request(path, { query: { ...query, page, page_size: 100 }, signal }), parse);
      if (count === undefined) count = dto.count;
      if (dto.count !== count || result.length + dto.results.length > dto.count || (dto.next && (!dto.results.length || page * 100 >= dto.count))) throw new ApiError('contract', 'Depreciation pagination changed unexpectedly. Reload the page.');
      for (const item of dto.results) {
        if (typeof item !== 'object' || item === null || !('id' in item) || typeof item.id !== 'string' || seen.has(item.id)) throw new ApiError('contract', 'Depreciation pagination returned duplicate or invalid records. Reload the page.');
        seen.add(item.id); result.push(item);
      }
      if (!dto.next) { if (result.length !== dto.count) throw new ApiError('contract', 'Depreciation data is incomplete. Reload the page.'); return result; }
    }
  }
  getPeriods(signal?: AbortSignal): Promise<AccountingPeriodRecord[]> { return this.allPages('/depreciation/periods/', row => mapAccountingPeriodDto(parseAccountingPeriodDto(row)), {}, signal); }
  getSchedules(signal?: AbortSignal): Promise<DepreciationScheduleRecord[]> { return this.allPages('/depreciation/schedules/', row => mapDepreciationScheduleDto(parseDepreciationScheduleDto(row)), {}, signal); }
  getEntries(filters: { asset?: string; period?: string }, signal?: AbortSignal): Promise<DepreciationEntryRecord[]> {
    const query: Record<string, string> = {};
    if (filters.asset) query.asset = filters.asset;
    if (filters.period) query.accounting_period = filters.period;
    return this.allPages('/depreciation/entries/', row => mapDepreciationEntryDto(parseDepreciationEntryDto(row)), query, signal);
  }
  async createPeriod(year: number, month: number): Promise<AccountingPeriodRecord> {
    return mapAccountingPeriodDto(parseAccountingPeriodDto(await this.api.request('/depreciation/periods/', { method: 'POST', body: { year, month } })));
  }
  async closePeriod(id: string): Promise<AccountingPeriodRecord> {
    return mapAccountingPeriodDto(parseAccountingPeriodDto(await this.api.request(`/depreciation/periods/${id}/close/`, { method: 'POST' })));
  }
  async createSchedule(assetId: string): Promise<DepreciationScheduleRecord> {
    return mapDepreciationScheduleDto(parseDepreciationScheduleDto(await this.api.request('/depreciation/schedules/', { method: 'POST', body: { asset_id: assetId } })));
  }
  async post(assetId: string, periodId: string): Promise<DepreciationEntryRecord> {
    return mapDepreciationEntryDto(parseDepreciationEntryDto(await this.api.request('/depreciation/entries/post/', { method: 'POST', body: { asset_id: assetId, period_id: periodId } })));
  }
}
