import { expect, it } from 'vitest';
import { parseDashboardMetrics } from './dashboardDtos';
import { formatExactMoney } from '../views/BackendDashboardView';

const response = {
  as_of: '2026-10-06T10:00:00Z', currency: 'NGN', scope: 'organization',
  portfolio: { registered_assets: 0, currently_held_assets: 0, capitalized_assets: 0, disposed_assets: 0 },
  financial: { capitalized_cost: '0.00', book_value: '9007199254740993.01', accumulated_depreciation: '0.00', current_month_posted_depreciation: '0.00', current_month_capitalized_cost: '0.00' },
  distributions: { status: [], category: [], department: [], location: [] },
  trends: { posted_depreciation: [], capitalizations: [] },
  operations: { open_work_orders: 0, critical_open_work_orders: 0, current_month_maintenance_cost: '0.00', requested_transfers: 0, approved_transfers: 0, pending_disposals: 0, approved_disposals: 0 },
  controls: { open_verification_exceptions: 0, open_assurance_findings: 0 }, recent_activity: [],
};
it('keeps zero and exact large Decimal strings without JS-number coercion', () => {
  const parsed = parseDashboardMetrics(response);
  expect(parsed.portfolio.registeredAssets).toBe(0);
  expect(parsed.financial.bookValue).toBe('9007199254740993.01');
});
it('rejects malformed money, missing metrics, and invalid scope', () => {
  expect(() => parseDashboardMetrics({ ...response, financial: { ...response.financial, book_value: 12 } })).toThrow();
  expect(() => parseDashboardMetrics({ ...response, scope: 'all-tenants' })).toThrow();
  expect(() => parseDashboardMetrics({ ...response, as_of: 'yesterday' })).toThrow();
  expect(() => parseDashboardMetrics({ ...response, currency: 'ABC' })).toThrow();
  expect(() => parseDashboardMetrics({ ...response, distributions: { ...response.distributions, status: [{ key: 'FUTURE_STATUS', label: 'Future', count: 1 }] } })).toThrow();
});
it('formats currency using exact integer grouping', () => {
  expect(formatExactMoney('9007199254740993.01', 'NGN')).toContain('9,007,199,254,740,993.01');
});
