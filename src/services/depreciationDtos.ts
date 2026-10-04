import { ApiError, isRecord } from './apiError';
import { uuidPattern } from './assetDtos';

export interface AccountingPeriodDto { id: string; year: number; month: number; status: string; opened_at: string; closed_at: string | null; closed_by: number | null; created_at: string; updated_at: string }
export interface AccountingPeriodRecord { id: string; year: number; month: number; status: 'OPEN' | 'CLOSED'; openedAt: string; closedAt: string | null; closedBy: number | null; createdAt: string; updatedAt: string }
export interface DepreciationScheduleDto { id: string; organization: string; asset_id: string; asset_tag: string; method: string; capitalized_cost: string; depreciable_base: string; residual_value: string; useful_life_months: number; start_date: string; end_date: string; periodic_depreciation: string; status: string; created_at: string; updated_at: string }
export interface DepreciationScheduleRecord { id: string; organizationId: string; assetId: string; assetTag: string; method: 'SLM'; capitalizedCost: string; depreciableBase: string; residualValue: string; usefulLifeMonths: number; startDate: string; endDate: string; periodicDepreciation: string; status: 'ACTIVE' | 'COMPLETE'; createdAt: string; updatedAt: string }
export interface DepreciationEntryDto { id: string; asset: string; asset_tag: string; schedule: string; accounting_period: string; year: number; month: number; opening_book_value: string; depreciation_amount: string; accumulated_depreciation: string; closing_book_value: string; posted_at: string; created_at: string; created_by: number | null }
export interface DepreciationEntryRecord { id: string; assetId: string; assetTag: string; scheduleId: string; periodId: string; year: number; month: number; openingBookValue: string; depreciationAmount: string; accumulatedDepreciation: string; closingBookValue: string; postedAt: string; createdAt: string; createdBy: number | null }
export interface PageDto<T> { count: number; next: string | null; previous: string | null; results: T[] }
function invalid(): never { throw new ApiError('contract', 'The depreciation API response does not match the expected AssetFlow format.'); }
function str(value: unknown): string { return typeof value === 'string' ? value : invalid(); }
function id(value: unknown): string { const result = str(value); return uuidPattern.test(result) ? result : invalid(); }
function nullableId(value: unknown): string | null { return value == null ? null : id(value); }
function nullableUserId(value: unknown): number | null { return value == null ? null : typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : invalid(); }
function decimal(value: unknown): string { return typeof value === 'string' && /^\d{1,18}\.\d{2}$/.test(value) ? value : invalid(); }
function positiveInteger(value: unknown): number { return typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : invalid(); }
function periodNumber(value: unknown, min: number, max: number): number { return typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max ? value : invalid(); }
function enumValue<T extends string>(value: unknown, values: readonly T[]): T { return typeof value === 'string' && values.includes(value as T) ? value as T : invalid(); }
export function parseAccountingPeriodDto(value: unknown): AccountingPeriodDto {
  if (!isRecord(value)) return invalid();
  return { id: id(value.id), year: periodNumber(value.year, 1900, 9999), month: periodNumber(value.month, 1, 12), status: enumValue(value.status, ['OPEN','CLOSED'] as const), opened_at: str(value.opened_at), closed_at: value.closed_at === null ? null : str(value.closed_at), closed_by: nullableUserId(value.closed_by), created_at: str(value.created_at), updated_at: str(value.updated_at) };
}
export function mapAccountingPeriodDto(dto: AccountingPeriodDto): AccountingPeriodRecord { return { id: dto.id, year: dto.year, month: dto.month, status: enumValue(dto.status, ['OPEN','CLOSED'] as const), openedAt: dto.opened_at, closedAt: dto.closed_at, closedBy: dto.closed_by, createdAt: dto.created_at, updatedAt: dto.updated_at }; }
export function parseDepreciationScheduleDto(value: unknown): DepreciationScheduleDto {
  if (!isRecord(value)) return invalid();
  const start = str(value.start_date), end = str(value.end_date);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) return invalid();
  return { id: id(value.id), organization: id(value.organization), asset_id: id(value.asset_id), asset_tag: str(value.asset_tag), method: enumValue(value.method, ['SLM'] as const), capitalized_cost: decimal(value.capitalized_cost), depreciable_base: decimal(value.depreciable_base), residual_value: decimal(value.residual_value), useful_life_months: positiveInteger(value.useful_life_months), start_date: start, end_date: end, periodic_depreciation: decimal(value.periodic_depreciation), status: enumValue(value.status, ['ACTIVE','COMPLETE'] as const), created_at: str(value.created_at), updated_at: str(value.updated_at) };
}
export function mapDepreciationScheduleDto(dto: DepreciationScheduleDto): DepreciationScheduleRecord { return { id: dto.id, organizationId: dto.organization, assetId: dto.asset_id, assetTag: dto.asset_tag, method: enumValue(dto.method, ['SLM'] as const), capitalizedCost: dto.capitalized_cost, depreciableBase: dto.depreciable_base, residualValue: dto.residual_value, usefulLifeMonths: dto.useful_life_months, startDate: dto.start_date, endDate: dto.end_date, periodicDepreciation: dto.periodic_depreciation, status: enumValue(dto.status, ['ACTIVE','COMPLETE'] as const), createdAt: dto.created_at, updatedAt: dto.updated_at }; }
export function parseDepreciationEntryDto(value: unknown): DepreciationEntryDto {
  if (!isRecord(value)) return invalid();
  return { id: id(value.id), asset: id(value.asset), asset_tag: str(value.asset_tag), schedule: id(value.schedule), accounting_period: id(value.accounting_period), year: periodNumber(value.year, 1900, 9999), month: periodNumber(value.month, 1, 12), opening_book_value: decimal(value.opening_book_value), depreciation_amount: decimal(value.depreciation_amount), accumulated_depreciation: decimal(value.accumulated_depreciation), closing_book_value: decimal(value.closing_book_value), posted_at: str(value.posted_at), created_at: str(value.created_at), created_by: nullableUserId(value.created_by) };
}
export function mapDepreciationEntryDto(dto: DepreciationEntryDto): DepreciationEntryRecord { return { id: dto.id, assetId: dto.asset, assetTag: dto.asset_tag, scheduleId: dto.schedule, periodId: dto.accounting_period, year: dto.year, month: dto.month, openingBookValue: dto.opening_book_value, depreciationAmount: dto.depreciation_amount, accumulatedDepreciation: dto.accumulated_depreciation, closingBookValue: dto.closing_book_value, postedAt: dto.posted_at, createdAt: dto.created_at, createdBy: dto.created_by }; }
export function parseDepreciationPageDto<T>(value: unknown, parse: (row: unknown) => T): PageDto<T> {
  if (!isRecord(value) || typeof value.count !== 'number' || !Number.isSafeInteger(value.count) || value.count < 0 || !Array.isArray(value.results) || !(value.next === null || typeof value.next === 'string') || !(value.previous === null || typeof value.previous === 'string')) return invalid();
  return { count: value.count, next: value.next, previous: value.previous, results: value.results.map(parse) };
}
