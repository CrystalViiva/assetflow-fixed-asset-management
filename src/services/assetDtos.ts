import { ApiError, isRecord } from './apiError';

// Wire DTOs describe the actual AssetSerializer, not the historical mock model.
export interface AssetDto {
  id: string;
  organization_id: string;
  organization_name: string;
  asset_tag: string;
  name: string;
  description: string;
  category_id: string;
  category_name: string;
  category_code: string;
  serial_number: string;
  model_number: string;
  manufacturer: string;
  status: string;
  condition: string;
  depreciation_method: string;
  created_at: string;
  updated_at: string;
  department_id: string | null;
  department_name: string | null;
  department_code: string | null;
  location_id: string | null;
  location_name: string | null;
  location_code: string | null;
  acquisition_date: string | null;
  capitalization_date: string | null;
  available_for_use_date: string | null;
  created_by_email: string | null;
  updated_by_email: string | null;
  purchase_cost: string;
  residual_value: string;
  accumulated_depreciation: string;
  current_book_value: string;
  useful_life_months: number | null;
}
export interface PageDto<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface AssetRecord {
  id: string; tag: string; name: string; description: string;
  organization: { id: string; name: string };
  category: { id: string; name: string; code: string };
  department: { id: string; name: string | null; code: string | null } | null;
  location: { id: string; name: string | null; code: string | null } | null;
  serialNumber: string; model: string; manufacturer: string;
  status: string; condition: string; depreciationMethod: string;
  acquisitionDate: string | null; capitalizationDate: string | null; availableForUseDate: string | null;
  purchaseCost: string; residualValue: string; accumulatedDepreciation: string; bookValue: string;
  usefulLifeMonths: number | null; createdAt: string; updatedAt: string;
}
export interface AssetPage {
  data: AssetRecord[]; total: number; page: number; pageSize: number; totalPages: number;
  hasNext: boolean; hasPrevious: boolean;
}
export const assetStatuses = ['DRAFT', 'PENDING_CAPITALIZATION', 'ACTIVE', 'IN_MAINTENANCE', 'TRANSFERRED', 'IMPAIRED', 'DISPOSED'];
const conditions = ['GOOD', 'FAIR', 'DAMAGED', 'CRITICAL', 'UNKNOWN'];
const methods = ['SLM', 'RBM', 'UOP', 'SYD'];
export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function contract(): never { throw new ApiError('contract', 'The API returned an unsupported asset response.'); }
function string(value: unknown): string { return typeof value === 'string' ? value : contract(); }
function nullable(value: unknown): string | null { return value == null ? null : string(value); }
function decimal(value: unknown): string {
  return typeof value === 'string' && /^\d{1,18}\.\d{2}$/.test(value) ? value : contract();
}
function enumValue(value: string, allowed: string[]): string {
  // Reject a future enum explicitly, rather than silently labelling it ACTIVE/SLM.
  return allowed.includes(value) ? value : contract();
}
export function parseAssetDto(value: unknown): AssetDto {
  if (!isRecord(value)) return contract();
  return {
    id: string(value.id),
    organization_id: string(value.organization_id),
    organization_name: string(value.organization_name),
    asset_tag: string(value.asset_tag),
    name: string(value.name),
    description: string(value.description),
    category_id: string(value.category_id),
    category_name: string(value.category_name),
    category_code: string(value.category_code),
    serial_number: string(value.serial_number),
    model_number: string(value.model_number),
    manufacturer: string(value.manufacturer),
    status: string(value.status),
    condition: string(value.condition),
    depreciation_method: string(value.depreciation_method),
    created_at: string(value.created_at),
    updated_at: string(value.updated_at),
    department_id: nullable(value.department_id),
    department_name: nullable(value.department_name),
    department_code: nullable(value.department_code),
    location_id: nullable(value.location_id),
    location_name: nullable(value.location_name),
    location_code: nullable(value.location_code),
    acquisition_date: nullable(value.acquisition_date),
    capitalization_date: nullable(value.capitalization_date),
    available_for_use_date: nullable(value.available_for_use_date),
    created_by_email: nullable(value.created_by_email),
    updated_by_email: nullable(value.updated_by_email),
    purchase_cost: decimal(value.purchase_cost),
    residual_value: decimal(value.residual_value),
    accumulated_depreciation: decimal(value.accumulated_depreciation),
    current_book_value: decimal(value.current_book_value),
    useful_life_months: value.useful_life_months === null ? null
      : typeof value.useful_life_months === 'number' && Number.isInteger(value.useful_life_months) && value.useful_life_months > 0
        ? value.useful_life_months : contract(),
  };
}
export function mapAssetDto(dto: AssetDto): AssetRecord {
  if (!uuidPattern.test(dto.id)) return contract();
  return {
    id: dto.id, tag: dto.asset_tag, name: dto.name, description: dto.description,
    organization: { id: dto.organization_id, name: dto.organization_name },
    category: { id: dto.category_id, name: dto.category_name, code: dto.category_code },
    department: dto.department_id ? { id: dto.department_id, name: dto.department_name, code: dto.department_code } : null,
    location: dto.location_id ? { id: dto.location_id, name: dto.location_name, code: dto.location_code } : null,
    serialNumber: dto.serial_number, model: dto.model_number, manufacturer: dto.manufacturer,
    status: enumValue(dto.status, assetStatuses), condition: enumValue(dto.condition, conditions),
    depreciationMethod: enumValue(dto.depreciation_method, methods),
    acquisitionDate: dto.acquisition_date, capitalizationDate: dto.capitalization_date, availableForUseDate: dto.available_for_use_date,
    purchaseCost: decimal(dto.purchase_cost), residualValue: decimal(dto.residual_value),
    accumulatedDepreciation: decimal(dto.accumulated_depreciation), bookValue: decimal(dto.current_book_value),
    usefulLifeMonths: dto.useful_life_months, createdAt: dto.created_at, updatedAt: dto.updated_at,
  };
}
export function parsePageDto<T>(value: unknown, parse: (row: unknown) => T): PageDto<T> {
  if (!isRecord(value) || typeof value.count !== 'number' || !Number.isSafeInteger(value.count) || value.count < 0
    || !Array.isArray(value.results)
    || !(value.next === null || typeof value.next === 'string')
    || !(value.previous === null || typeof value.previous === 'string')) return contract();
  return { count: value.count, next: value.next, previous: value.previous, results: value.results.map(parse) };
}
export function mapAssetPage(dto: PageDto<AssetDto>, page: number, pageSize: number): AssetPage {
  return { data: dto.results.map(mapAssetDto), total: dto.count, page, pageSize,
    totalPages: Math.max(1, Math.ceil(dto.count / pageSize)), hasNext: dto.next !== null, hasPrevious: dto.previous !== null };
}
// String grouping is display-only and retains every fractional digit. The asset API exposes no currency.
export function formatDecimal(value: string): string {
  const [whole, fraction] = decimal(value).split('.');
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + fraction;
}
