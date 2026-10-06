import { ApiClient } from './apiClient';
import { ApiError, isRecord } from './apiError';
import { parsePageDto, uuidPattern } from './assetDtos';

export type AuditJson = string | number | boolean | null | AuditJson[] | { [key: string]: AuditJson };
export interface AuditEvent {
  id: string; timestamp: string; actorEmail: string | null; action: string;
  entityType: string; entityId: string; changes: Record<string, AuditJson>; metadata: Record<string, AuditJson>;
}
export interface AuditFilters {
  page: number; pageSize: number; action: string; entityType: string; entityId: string;
  actor: string; search: string; dateFrom: string; dateTo: string; ordering: 'timestamp' | '-timestamp';
}
export interface AuditPage { count: number; next: string | null; previous: string | null; results: AuditEvent[] }
const fail = (): never => { throw new ApiError('contract', 'The audit API response does not match the expected AssetFlow format.'); };
const string = (v: unknown): string => typeof v === 'string' ? v : fail();
const nullableString = (v: unknown): string | null => v === null ? null : string(v);
const sensitive = /(password|token|authorization|api[_-]?key|secret|credential|cookie)/i;
export function safeAuditJson(value: unknown, depth = 0, key = ''): AuditJson {
  if (sensitive.test(key)) return '[REDACTED]';
  if (depth > 8) return '[Nested value omitted]';
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(item => safeAuditJson(item, depth + 1));
  if (isRecord(value)) {
    const result: Record<string, AuditJson> = {};
    for (const [name, item] of Object.entries(value)) result[name] = safeAuditJson(item, depth + 1, name);
    return result;
  }
  return fail();
}
function jsonObject(value: unknown): Record<string, AuditJson> {
  if (!isRecord(value)) return fail();
  return safeAuditJson(value) as Record<string, AuditJson>;
}
export function parseAuditEvent(value: unknown): AuditEvent {
  if (!isRecord(value)) return fail();
  const id = string(value.id), timestamp = string(value.timestamp);
  if (!uuidPattern.test(id) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp) || Number.isNaN(Date.parse(timestamp))) return fail();
  const actorEmail = nullableString(value.actor_email);
  if (actorEmail !== null && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(actorEmail)) return fail();
  const action = string(value.action), entityType = string(value.entity_type), entityId = string(value.entity_id);
  if (!action || !entityType || !entityId) return fail();
  return { id, timestamp, actorEmail, action, entityType, entityId,
    changes: jsonObject(value.changes), metadata: jsonObject(value.metadata) };
}
export class DjangoAuditRepository {
  constructor(private readonly api: ApiClient) {}
  async events(filters: AuditFilters, signal?: AbortSignal): Promise<AuditPage> {
    if (!Number.isInteger(filters.page) || filters.page < 1 || !Number.isInteger(filters.pageSize) || filters.pageSize < 1
      || (filters.ordering !== 'timestamp' && filters.ordering !== '-timestamp')) throw new ApiError('validation', 'Invalid audit query.');
    const dto = parsePageDto(await this.api.request('/audit/events/', { signal, query: {
      page: filters.page, page_size: Math.min(filters.pageSize, 100), action: filters.action,
      entity_type: filters.entityType, entity_id: filters.entityId, actor: filters.actor,
      search: filters.search, date_from: filters.dateFrom, date_to: filters.dateTo, ordering: filters.ordering,
    } }), parseAuditEvent);
    return { count: dto.count, next: dto.next, previous: dto.previous, results: dto.results };
  }
}
