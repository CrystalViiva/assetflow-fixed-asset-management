import { ApiError, isRecord } from './apiError';
import { uuidPattern } from './assetDtos';

export interface DashboardGroup { key: string; label: string; count: number; bookValue?: string }
export interface DashboardActivity { id: string; timestamp: string; actor: string | null; action: string; entityType: string; entityId: string }
export interface DashboardMetrics {
  asOf: string; currency: string; scope: 'organization' | 'department';
  portfolio: { registeredAssets: number; currentlyHeldAssets: number; capitalizedAssets: number; disposedAssets: number };
  financial: { capitalizedCost: string; bookValue: string; accumulatedDepreciation: string; currentMonthPostedDepreciation: string; currentMonthCapitalizedCost: string };
  distributions: { status: DashboardGroup[]; category: DashboardGroup[]; department: DashboardGroup[]; location: DashboardGroup[] };
  trends: { postedDepreciation: { period: string; amount: string }[]; capitalizations: { period: string; amount: string }[] };
  operations: { openWorkOrders: number; criticalOpenWorkOrders: number; currentMonthMaintenanceCost: string; requestedTransfers: number; approvedTransfers: number; pendingDisposals: number; approvedDisposals: number };
  controls: { openVerificationExceptions: number; openAssuranceFindings: number };
  recentActivity: DashboardActivity[];
}
const fail = (): never => { throw new ApiError('contract', 'The dashboard response does not match the supported AssetFlow format.'); };
const currencyCodes = new Set(['NGN', 'USD', 'GBP', 'EUR', 'ZAR', 'GHS', 'KES', 'XOF', 'XAF', 'AED', 'SAR', 'CAD', 'AUD', 'CHF', 'CNY', 'JPY', 'INR']);
const assetStatuses = new Set(['DRAFT', 'PENDING_CAPITALIZATION', 'ACTIVE', 'IN_MAINTENANCE', 'TRANSFERRED', 'IMPAIRED', 'DISPOSED']);
const object = (v: unknown): Record<string, unknown> => isRecord(v) ? v : fail();
const string = (v: unknown): string => typeof v === 'string' ? v : fail();
const integer = (v: unknown): number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 ? v : fail();
const money = (v: unknown): string => typeof v === 'string' && /^\d+\.\d{2}$/.test(v) ? v : fail();
const timestamp = (v: unknown): string => { const s = string(v); return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(s) && !Number.isNaN(Date.parse(s)) ? s : fail(); };
function groups(v: unknown, values: boolean, kind: 'status' | 'reference'): DashboardGroup[] { if (!Array.isArray(v)) return fail(); return v.map(item => { const row = object(item); const base = { key: string(row.key), label: string(row.label), count: integer(row.count) }; if (!base.key || !base.label || (kind === 'status' && !assetStatuses.has(base.key)) || (kind === 'reference' && base.key !== 'UNASSIGNED' && !uuidPattern.test(base.key))) return fail(); return values ? { ...base, bookValue: money(row.book_value) } : base; }); }
function series(v: unknown): { period: string; amount: string }[] { if (!Array.isArray(v) || v.length > 12) return fail(); const rows = v.map(item => { const row = object(item), period = string(row.period); if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) return fail(); return { period, amount: money(row.amount) }; }); if (new Set(rows.map(row => row.period)).size !== rows.length || rows.some((row, index) => index > 0 && rows[index - 1].period >= row.period)) return fail(); return rows; }
export function parseDashboardMetrics(value: unknown): DashboardMetrics {
  const root = object(value), p = object(root.portfolio), f = object(root.financial), d = object(root.distributions), t = object(root.trends), o = object(root.operations), c = object(root.controls);
  const scope = string(root.scope); if (scope !== 'organization' && scope !== 'department') return fail();
  const currency = string(root.currency); if (!currencyCodes.has(currency)) return fail();
  const activity = root.recent_activity; if (!Array.isArray(activity) || activity.length > 8) return fail();
  return {
    asOf: timestamp(root.as_of), currency, scope,
    portfolio: { registeredAssets: integer(p.registered_assets), currentlyHeldAssets: integer(p.currently_held_assets), capitalizedAssets: integer(p.capitalized_assets), disposedAssets: integer(p.disposed_assets) },
    financial: { capitalizedCost: money(f.capitalized_cost), bookValue: money(f.book_value), accumulatedDepreciation: money(f.accumulated_depreciation), currentMonthPostedDepreciation: money(f.current_month_posted_depreciation), currentMonthCapitalizedCost: money(f.current_month_capitalized_cost) },
    distributions: { status: groups(d.status, false, 'status'), category: groups(d.category, true, 'reference'), department: groups(d.department, true, 'reference'), location: groups(d.location, true, 'reference') },
    trends: { postedDepreciation: series(t.posted_depreciation), capitalizations: series(t.capitalizations) },
    operations: { openWorkOrders: integer(o.open_work_orders), criticalOpenWorkOrders: integer(o.critical_open_work_orders), currentMonthMaintenanceCost: money(o.current_month_maintenance_cost), requestedTransfers: integer(o.requested_transfers), approvedTransfers: integer(o.approved_transfers), pendingDisposals: integer(o.pending_disposals), approvedDisposals: integer(o.approved_disposals) },
    controls: { openVerificationExceptions: integer(c.open_verification_exceptions), openAssuranceFindings: integer(c.open_assurance_findings) },
    recentActivity: activity.map(item => { const row = object(item), id = string(row.id), actor = row.actor, action = string(row.action), entityType = string(row.entity_type), entityId = string(row.entity_id); if (!uuidPattern.test(id) || (actor !== null && (typeof actor !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(actor))) || !action || !entityType || !entityId) return fail(); return { id, timestamp: timestamp(row.timestamp), actor: actor as string | null, action, entityType, entityId }; }),
  };
}
