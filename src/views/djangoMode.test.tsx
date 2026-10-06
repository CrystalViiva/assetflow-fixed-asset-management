import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('../services/config', () => ({ dataSource:'django',apiBase:'/api/v1' }));
import { AuthProvider } from '../auth/AuthProvider';
import { AuthenticatedApplication } from '../auth/ApplicationRoot';
import { Session } from '../services/session';
import { apiClient } from '../services/runtime';
import { MockAssetRepository } from '../services/assetRepository';
import { assetDto, identity, json } from '../test/fixtures';

const emptyPage = { count:0,next:null,previous:null,results:[] };
const dashboardData = { as_of:'2026-10-06T10:00:00Z',currency:'NGN',scope:'organization',portfolio:{registered_assets:0,currently_held_assets:0,capitalized_assets:0,disposed_assets:0},financial:{capitalized_cost:'0.00',book_value:'0.00',accumulated_depreciation:'0.00',current_month_posted_depreciation:'0.00',current_month_capitalized_cost:'0.00'},distributions:{status:[],category:[],department:[],location:[]},trends:{posted_depreciation:[],capitalizations:[]},operations:{open_work_orders:0,critical_open_work_orders:0,current_month_maintenance_cost:'0.00',requested_transfers:0,approved_transfers:0,pending_disposals:0,approved_disposals:0},controls:{open_verification_exceptions:0,open_assurance_findings:0},recent_activity:[] };
const categoryPage = { count:1,next:null,previous:null,results:[{ id:assetDto.category_id,organization_id:assetDto.organization_id,
  organization_name:'Test Organization',name:'Equipment',code:'EQ',is_active:true,description:'',default_useful_life_months:120,
  default_depreciation_method:'SLM',capitalization_threshold:'0.00',created_at:'2026-01-01T00:00:00Z',updated_at:'2026-01-01T00:00:00Z' }] };
function backendData(fetcher: ReturnType<typeof vi.fn<typeof fetch>>, assetResponse: (url: string) => Response | Promise<Response>) {
  fetcher.mockImplementation(async input => {
    const url = String(input);
    if (url.includes('/dashboard/metrics/')) return json(dashboardData);
    if (url.includes('/assets/categories/')) return json(categoryPage);
    if (url.includes('/depreciation/')) return json(emptyPage);
    if (url.includes('/assets/maintenance-plans/') || url.includes('/assets/work-orders/') || url.includes('/assets/maintenance-costs/') || url.includes('/assets/maintenance-records/')) return json(emptyPage);
    if (url.includes('/departments/') || url.includes('/locations/') || url.includes('/assets/acquisitions/')) return json(emptyPage);
    return assetResponse(url);
  });
}

afterEach(() => { vi.unstubAllGlobals(); window.location.hash = ''; sessionStorage.clear(); });
async function renderRealApp() {
  window.location.hash = '#all-assets';
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false } } });
  const session = new Session(apiClient,sessionStorage,() => client.clear());
  const fetcher = vi.fn<typeof fetch>(); vi.stubGlobal('fetch',fetcher);
  await session.initialize(); fetcher.mockResolvedValueOnce(json({ access:'test-access',refresh:'test-refresh' })).mockResolvedValueOnce(json(identity));
  await session.login(identity.email,'test-password'); fetcher.mockReset();
  backendData(fetcher, () => json({ count:1,next:null,previous:null,results:[assetDto] }));
  vi.spyOn(window,'scrollTo').mockImplementation(() => {});
  render(<QueryClientProvider client={client}><AuthProvider value={session}><AuthenticatedApplication /></AuthProvider></QueryClientProvider>);
  return { session,client,fetcher };
}
it('real-mode shell shows real identity, no mock alerts/actions, and logs out', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator', {}, { timeout: 10000 });
  expect(screen.getByText(identity.email)).toBeTruthy(); expect(screen.queryByText('Demo Finance Lead')).toBeNull();
  for (const text of ['1,284','4 pending','2 overdue','Lagos Corporate Facility']) expect(screen.queryByText(text)).toBeNull();
  expect(screen.queryByRole('button',{ name:'Actions' })).toBeNull(); expect(screen.queryByTitle('Notifications')).toBeNull();
  fireEvent.click(screen.getByRole('button',{ name:'Sign out' }));
  expect(await screen.findByRole('heading',{ name:/control the complete lifecycle of every asset/i })).toBeTruthy(); expect(c.client.getQueryCache().getAll()).toHaveLength(0);
}, 15000);
it('Django dashboard uses live metrics and never renders mock enterprise figures', async () => {
  await renderRealApp(); await screen.findByText('Office generator', {}, { timeout: 10000 });
  fireEvent.click(screen.getByRole('button',{ name:'Dashboard' }));
  expect(await screen.findByRole('heading',{ name:'Operational dashboard' })).toBeTruthy();
  expect(await screen.findByText('0 capitalized · 0 disposed')).toBeTruthy();
  expect(screen.getByText(/Live Django/)).toBeTruthy();
  expect(screen.queryByText('Office generator')).toBeNull();
}, 15000);
it('Django dashboard API failure stays an error and does not substitute demonstration analytics', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator');
  c.fetcher.mockImplementation(async input => String(input).includes('/dashboard/metrics/') ? Response.json({ error:{code:'API_ERROR',message:'failure'} },{status:503}) : json(emptyPage));
  fireEvent.click(screen.getByRole('button',{ name:'Dashboard' }));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('could not complete'));
  for (const demo of ['1,284','Demo Finance Lead','₦48.2M','Lagos Corporate Facility']) expect(screen.queryByText(demo)).toBeNull();
});
it('Django Audit Log route renders its role-scoped real screen without mock rows', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator');
  fireEvent.click(screen.getByRole('button',{name:'Audit Log'}));
  expect(await screen.findByRole('heading',{name:'Audit Log'})).toBeTruthy();
  expect(screen.getByRole('status').textContent).toContain('administrators and asset managers');
  expect(c.fetcher.mock.calls.some(call=>String(call[0]).includes('/audit/events/'))).toBe(false);
});
it('Django depreciation route loads only backend state and never the mock posting simulator', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator');
  fireEvent.click(screen.getAllByRole('button',{ name:'Depreciation' }).at(-1)!);
  expect(await screen.findByRole('heading',{ name:'Depreciation & Accounting Periods' })).toBeTruthy();
  expect(await screen.findByText('No accounting periods')).toBeTruthy();
  expect(c.fetcher.mock.calls.some(call => String(call[0]).includes('/depreciation/periods/'))).toBe(true);
  expect(screen.queryByText(/executed successfully/)).toBeNull();
});
it('Django depreciation page labels backend ledger values as posted and uses exact amounts', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator');
  const period = { id:'11111111-1111-4111-8111-111111111111', year:2026, month:1, status:'OPEN', opened_at:'2026-01-01T00:00:00Z', closed_at:null, closed_by:null, created_at:'2026-01-01T00:00:00Z', updated_at:'2026-01-01T00:00:00Z' };
  const schedule = { id:'22222222-2222-4222-8222-222222222222', organization:assetDto.organization_id, asset_id:assetDto.id, asset_tag:assetDto.asset_tag, method:'SLM', capitalized_cost:'1001.00', depreciable_base:'901.00', residual_value:'100.00', useful_life_months:36, start_date:'2026-01-02', end_date:'2028-12-31', periodic_depreciation:'25.03', status:'ACTIVE', created_at:'2026-01-01T00:00:00Z', updated_at:'2026-01-01T00:00:00Z' };
  const entry = { id:'33333333-3333-4333-8333-333333333333', asset:assetDto.id, asset_tag:assetDto.asset_tag, schedule:schedule.id, accounting_period:period.id, year:2026, month:1, opening_book_value:'1001.00', depreciation_amount:'25.03', accumulated_depreciation:'25.03', closing_book_value:'975.97', posted_at:'2026-01-31T00:00:00Z', created_at:'2026-01-31T00:00:00Z', created_by:1 };
  const laterEntry = { ...entry, id:'44444444-4444-4444-8444-444444444444', month:2, accounting_period:'55555555-5555-4555-8555-555555555555', opening_book_value:'975.97', depreciation_amount:'25.03', accumulated_depreciation:'50.06', closing_book_value:'950.94' };
  c.fetcher.mockImplementation(async input => {
    const url = String(input);
    if (url.includes('/depreciation/periods/')) return json({ count:1,next:null,previous:null,results:[period] });
    if (url.includes('/depreciation/schedules/')) return json({ count:1,next:null,previous:null,results:[schedule] });
    if (url.includes('/depreciation/entries/')) return url.includes(`accounting_period=${period.id}`)
      ? json({ count:1,next:null,previous:null,results:[entry] })
      : json({ count:2,next:null,previous:null,results:[entry,laterEntry] });
    if (url.includes('/assets/categories/')) return json(categoryPage);
    if (url.includes('/departments/') || url.includes('/locations/') || url.includes('/assets/acquisitions/')) return json(emptyPage);
    return json({ count:1,next:null,previous:null,results:[assetDto] });
  });
  fireEvent.click(screen.getAllByRole('button',{ name:'Depreciation' })[0]);
  expect(await screen.findByText(/POSTED · Ledger entry/)).toBeTruthy();
  expect(screen.getAllByText('25.03').length).toBeGreaterThan(0); expect(screen.getAllByText('975.97').length).toBeGreaterThan(0);
  expect(screen.getByText(/Nominal periodic amount · backend schedule/)).toBeTruthy();
  expect(screen.getByText('2026-02 · POSTED')).toBeTruthy();
  expect(screen.queryByText(/PROJECTED/)).toBeNull();
  expect(screen.queryByText(/successfully/)).toBeNull();
});
it('real-mode asset UUID opens only the real detail overview', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator'); backendData(c.fetcher, () => json(assetDto));
  fireEvent.click(screen.getByRole('button',{ name:'REAL-001' }));
  expect(await screen.findByRole('heading',{ name:'REAL-001 - Office generator' })).toBeTruthy();
  expect(window.location.hash).toBe(`#asset-detail/${assetDto.id}`);
  expect(screen.getAllByRole('button',{ name:/Generic documents/ })).toHaveLength(1);
  fireEvent.click(screen.getAllByRole('button',{ name:'Maintenance' }).at(-1)!);
  expect(await screen.findByText('No maintenance plans.')).toBeTruthy();
  fireEvent.click(screen.getAllByRole('button',{ name:'Depreciation' }).at(-1)!);
  expect(await screen.findByText('No depreciation schedule')).toBeTruthy();
  expect(screen.queryByText(/Monthly Depreciation Posting Run executed successfully/)).toBeNull();
  act(() => c.session.logout());
});
it('guards the mock repository from accidental use in Django mode', async () => {
  const repository = new MockAssetRepository();
  await expect(repository.getAssets()).rejects.toThrow('Mock data is unavailable');
  await expect(repository.getUsers()).rejects.toThrow('Mock data is unavailable');
  await expect(repository.resetToDefaultData()).rejects.toThrow('Mock data is unavailable');
});
