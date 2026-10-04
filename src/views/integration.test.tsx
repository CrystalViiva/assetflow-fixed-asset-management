import { StrictMode, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../auth/AuthProvider';
import { AuthenticatedApplication } from '../auth/ApplicationRoot';
import { Session, REFRESH_KEY } from '../services/session';
import { apiClient } from '../services/runtime';
import { ApiClient } from '../services/apiClient';
import { assetDto, deferred, identity, json } from '../test/fixtures';
import { BackendAssetRegister, updateAssetFilters } from './BackendAssetRegister';
import { BackendAssetDetail } from './BackendAssetDetail';
import { BackendAssetCreate } from './BackendAssetCreate';
import { LoginView } from './LoginView';
import { defaultAssetQuery } from '../services/djangoApiBridge';

afterEach(() => vi.unstubAllGlobals());
function frame(session: Session, client: QueryClient, children: ReactNode) {
  return <QueryClientProvider client={client}><AuthProvider value={session}>{children}</AuthProvider></QueryClientProvider>;
}
const emptyPage = { count:0,next:null,previous:null,results:[] };
const categoryPage = { count:1,next:null,previous:null,results:[{ id:assetDto.category_id,organization_id:assetDto.organization_id,
  organization_name:'Test Organization',name:'Equipment',code:'EQ',is_active:true,description:'',default_useful_life_months:120,
  default_depreciation_method:'SLM',capitalization_threshold:'0.00',created_at:'2026-01-01T00:00:00Z',updated_at:'2026-01-01T00:00:00Z' }] };
function backendData(fetcher: ReturnType<typeof vi.fn<typeof fetch>>, primary: (url: string) => Response | Promise<Response>) {
  fetcher.mockImplementation(async input => {
    const url = String(input);
    if (url.includes('/assets/categories/')) return json(categoryPage);
    if (url.includes('/departments/') || url.includes('/locations/') || url.includes('/assets/acquisitions/')) return json(emptyPage);
    return primary(url);
  });
}
async function authenticated(role = identity.role) {
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false,gcTime:0 } } });
  const session = new Session(apiClient,sessionStorage,() => client.clear());
  const fetcher = vi.fn<typeof fetch>(); vi.stubGlobal('fetch',fetcher);
  await session.initialize();
  fetcher.mockResolvedValueOnce(json({ access:'test-access-1',refresh:'test-refresh-1' })).mockResolvedValueOnce(json({ ...identity, role }));
  await session.login(identity.email,'test-password'); fetcher.mockReset();
  return { client,session,fetcher };
}
describe('login and application boundary', () => {
  it('submits credentials by keyboard and exposes authenticated identity', async () => {
    const client = new QueryClient(); const fetcher = vi.fn<typeof fetch>();
    const session = new Session(new ApiClient('/api/v1',fetcher),sessionStorage,() => client.clear());
    fetcher.mockResolvedValueOnce(json({ access:'test-access',refresh:'test-refresh' })).mockResolvedValueOnce(json(identity));
    function Probe() { const auth = useAuth(); return auth.authenticated ? <p>{auth.user?.email}</p> : <LoginView />; }
    render(frame(session,client,<Probe />)); const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email'),identity.email); await user.type(screen.getByLabelText('Password'),'test-password{Enter}');
    expect(await screen.findByText(identity.email)).toBeTruthy();
  });
  it.each(['invalid','network'])('shows %s login failure with an accessible error', async mode => {
    const client = new QueryClient(); const fetcher = vi.fn<typeof fetch>();
    const session = new Session(new ApiClient('/api/v1',fetcher),sessionStorage,() => client.clear());
    if (mode === 'invalid') fetcher.mockResolvedValue(json({},401)); else fetcher.mockRejectedValue(new TypeError('offline'));
    render(frame(session,client,<LoginView />));
    fireEvent.change(screen.getByLabelText('Email'),{ target:{ value:identity.email } });
    fireEvent.change(screen.getByLabelText('Password'),{ target:{ value:'test-password' } });
    fireEvent.click(screen.getByRole('button',{ name:'Sign in' }));
    expect((await screen.findByRole('alert')).textContent).toContain(mode === 'invalid' ? 'Check your email and password' : 'Unable to reach');
  });
  it('does not flash the protected shell during session restoration, including StrictMode', async () => {
    const pending = deferred<Response>(); const fetcher = vi.fn<typeof fetch>().mockReturnValue(pending.promise);
    sessionStorage.setItem(REFRESH_KEY,'test-refresh'); const client = new QueryClient();
    const session = new Session(new ApiClient('/api/v1',fetcher),sessionStorage,() => client.clear());
    render(<StrictMode>{frame(session,client,<AuthenticatedApplication />)}</StrictMode>);
    expect(screen.getByRole('status').textContent).toContain('Restoring'); expect(screen.queryByText('Asset Register')).toBeNull();
    await act(async () => { pending.resolve(json({},401)); });
    expect(await screen.findByRole('button',{ name:'Sign in' })).toBeTruthy(); expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
describe('real asset register', () => {
  it('renders loading then successful server data and navigates by UUID', async () => {
    const c = await authenticated(); const pending = deferred<Response>();
    backendData(c.fetcher, url => url.includes('/assets/') ? pending.promise : json(emptyPage));
    const select = vi.fn(); render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={select} />));
    expect(screen.getByText('Loading assets…')).toBeTruthy();
    await act(async () => { pending.resolve(json({ count:1,next:null,previous:null,results:[assetDto] })); });
    fireEvent.click(await screen.findByRole('button',{ name:'REAL-001' })); expect(select).toHaveBeenCalledWith(assetDto.id);
    expect(screen.getByText('999,999,999,999,999,999.99')).toBeTruthy(); expect(screen.queryByText('AST-000002')).toBeNull();
  });
  it('renders empty results', async () => {
    const c = await authenticated(); backendData(c.fetcher, () => json(emptyPage));
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    expect(await screen.findByText('No assets match these filters.')).toBeTruthy(); expect(screen.getByText('0 assets · Page 1 of 1')).toBeTruthy();
  });
  it.each([403,500])('renders HTTP %s without mock fallback', async status => {
    const c = await authenticated(); backendData(c.fetcher, () => json({},status));
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(screen.queryByText('AST-000002')).toBeNull();
  });
  it('paginates and resets page for search and filter changes', async () => {
    const c = await authenticated();
    backendData(c.fetcher, async url => { const page = new URL(url,'http://localhost').searchParams.get('page');
      return json({ count:26,next:page === '1' ? '/assets/?page=2' : null,previous:page === '2' ? '/assets/?page=1' : null,results:[assetDto] }); });
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    await screen.findByText('26 assets · Page 1 of 2'); fireEvent.click(screen.getByRole('button',{ name:'Next' }));
    await screen.findByText('26 assets · Page 2 of 2');
    fireEvent.change(screen.getByLabelText('Search assets'),{ target:{ value:'pump' } }); await screen.findByText('26 assets · Page 1 of 2');
    expect(String(c.fetcher.mock.calls.at(-1)?.[0])).toContain('page=1'); expect(String(c.fetcher.mock.calls.at(-1)?.[0])).toContain('search=pump');
    fireEvent.click(screen.getByRole('button',{ name:'Next' })); await screen.findByText('26 assets · Page 2 of 2');
    fireEvent.change(screen.getByLabelText('Status'),{ target:{ value:'ACTIVE' } }); await screen.findByText('26 assets · Page 1 of 2');
    expect(String(c.fetcher.mock.calls.at(-1)?.[0])).toContain('status=ACTIVE');
  });
  it('ignores stale responses when searches change rapidly', async () => {
    const c = await authenticated(); const slow = deferred<Response>();
    backendData(c.fetcher, async url => url.includes('search=old') ? slow.promise
      : json({ count:1,next:null,previous:null,results:[{ ...assetDto,name:'Current result' }] }));
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    await screen.findByText('Current result'); fireEvent.change(screen.getByLabelText('Search assets'),{ target:{ value:'old' } });
    fireEvent.change(screen.getByLabelText('Search assets'),{ target:{ value:'new' } }); await screen.findByText('Current result');
    await act(async () => { slow.resolve(json({ count:1,next:null,previous:null,results:[{ ...assetDto,name:'Stale result' }] })); });
    expect(screen.queryByText('Stale result')).toBeNull();
  });
  it.each(['search','status','category','department','location','ordering','pageSize'] as const)('%s change resets pagination atomically', field => {
    expect(updateAssetFilters({ ...defaultAssetQuery,page:3 },{ [field]:field === 'pageSize' ? 50 : 'test' }).page).toBe(1);
  });
});
describe('real asset detail and cache security', () => {
  it('renders loading then real overview, null fields, and disabled pending tabs', async () => {
    const c = await authenticated(); const pending = deferred<Response>();
    backendData(c.fetcher, url => url.includes(`/assets/${assetDto.id}/`) ? pending.promise : json(emptyPage));
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={() => {}} />));
    expect(screen.getByRole('status').textContent).toContain('Loading asset details');
    await act(async () => { pending.resolve(json(assetDto)); });
    expect(await screen.findByRole('heading',{ name:'REAL-001 - Office generator' })).toBeTruthy();
    const tabs = screen.getAllByRole('button',{ name:/Integration pending/ }); expect(tabs).toHaveLength(5);
    for (const tab of tabs) expect(tab.hasAttribute('disabled')).toBe(true);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
  it.each([404,403,500])('handles detail HTTP %s', async status => {
    const c = await authenticated(); backendData(c.fetcher, () => json({},status));
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={() => {}} />));
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(screen.queryByText('Office generator')).toBeNull();
  });
  it('clears cached user A assets and renders no A data when user B logs in', async () => {
    const c = await authenticated();
    backendData(c.fetcher, () => json({ count:1,next:null,previous:null,results:[{ ...assetDto,name:'User A private asset' }] }));
    function Boundary() { const auth = useAuth(); return auth.authenticated ? <BackendAssetRegister key={auth.generation} globalSearch="" onSelectAsset={() => {}} /> : <p>Signed out</p>; }
    render(frame(c.session,c.client,<Boundary />)); await screen.findByText('User A private asset');
    act(() => c.session.logout()); expect(c.client.getQueryCache().getAll()).toHaveLength(0);
    expect(screen.queryByText('User A private asset')).toBeNull(); expect(sessionStorage.getItem(REFRESH_KEY)).toBeNull();
    c.fetcher.mockReset(); c.fetcher.mockResolvedValueOnce(json({ access:'test-access-b',refresh:'test-refresh-b' })).mockResolvedValueOnce(json({ ...identity,id:2,email:'two@example.test' }));
    backendData(c.fetcher, () => json(emptyPage));
    await act(async () => { await c.session.login('two@example.test','test-password'); });
    expect(screen.queryByText('User A private asset')).toBeNull(); await screen.findByText('No assets match these filters.');
    expect(c.session.getSnapshot().user?.id).toBe(2);
  });
});

describe('Django asset creation form', () => {
  it('uses real selected UUIDs and the staged API workflow, then navigates to the real asset', async () => {
    const c = await authenticated('ASSET_MANAGER');
    const deptId = 'ca291303-1e7a-4bc1-a563-8ba4f1b60d50';
    const locationId = 'a2ea38f0-989c-462f-947f-501c21ef6b55';
    const acquisitionId = '91f3ad08-4110-4559-b52f-839465836eee';
    const requests: Array<{ url:string; init:RequestInit | undefined }> = [];
    c.fetcher.mockImplementation(async (input, init) => {
      const url = String(input); requests.push({ url, init });
      if (url.includes('/assets/categories/')) return json(categoryPage);
      if (url.includes('/departments/')) return json({ count:1,next:null,previous:null,results:[{ id:deptId,organization_id:assetDto.organization_id,name:'Operations',code:'OPS',is_active:true }] });
      if (url.includes('/locations/')) return json({ count:1,next:null,previous:null,results:[{ id:locationId,organization_id:assetDto.organization_id,name:'Main Plant',code:'PLANT',is_active:true }] });
      if (url.endsWith(`/assets/acquisitions/${acquisitionId}/capitalize/`)) return json({ id:acquisitionId,organization_id:assetDto.organization_id,
        asset_id:assetDto.id,asset_tag:'F2-UI-001',asset_name:'UI Pump',vendor_name:'',invoice_number:'',acquisition_date:'2026-01-01',capitalization_date:'2026-01-02',
        currency:'NGN',purchase_price:'1000.01',freight_cost:'0.99',installation_cost:'0.00',civil_works_cost:'0.00',other_capitalizable_cost:'0.00',
        total_cost:'1001.00',reference:'',notes:'',status:'CAPITALIZED',created_at:'2026-01-02T00:00:00Z',updated_at:'2026-01-02T00:00:00Z' });
      if (url.includes('/assets/acquisitions/') && init?.method === 'POST') return json({ id:acquisitionId,organization_id:assetDto.organization_id,
        asset_id:assetDto.id,asset_tag:'F2-UI-001',asset_name:'UI Pump',vendor_name:'',invoice_number:'',acquisition_date:'2026-01-01',capitalization_date:'2026-01-02',
        currency:'NGN',purchase_price:'1000.01',freight_cost:'0.99',installation_cost:'0.00',civil_works_cost:'0.00',other_capitalizable_cost:'0.00',
        total_cost:'1001.00',reference:'',notes:'',status:'DRAFT',created_at:'2026-01-02T00:00:00Z',updated_at:'2026-01-02T00:00:00Z' },201);
      if (url.includes('/assets/acquisitions/')) return json(emptyPage);
      if (url === '/api/v1/assets/' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        return json({ ...assetDto,id:assetDto.id,asset_tag:body.asset_tag,name:body.name,status:'DRAFT',category_id:body.category_id,
          department_id:body.department_id,department_name:'Operations',department_code:'OPS',location_id:body.location_id,location_name:'Main Plant',location_code:'PLANT',
          acquisition_date:body.acquisition_date,capitalization_date:null,available_for_use_date:null,purchase_cost:body.purchase_cost,residual_value:body.residual_value,
          useful_life_months:body.useful_life_months,depreciation_method:'SLM' },201);
      }
      if (url === `/api/v1/assets/${assetDto.id}/`) return json({ ...assetDto,asset_tag:'F2-UI-001',name:'UI Pump',status:'ACTIVE',
        acquisition_date:'2026-01-01',capitalization_date:'2026-01-02',available_for_use_date:'2026-01-02',purchase_cost:'1001.00',residual_value:'0.00',useful_life_months:36 });
      throw new Error(`Unexpected test request ${url}`);
    });
    const navigate = vi.fn();
    render(frame(c.session,c.client,<BackendAssetCreate onNavigate={navigate} />));
    await waitFor(() => expect(screen.getByLabelText('Category *').hasAttribute('disabled')).toBe(false));
    fireEvent.change(screen.getByLabelText('Asset name *'),{ target:{ value:'UI Pump' } });
    fireEvent.change(screen.getByLabelText('Asset tag *'),{ target:{ value:'F2-UI-001' } });
    fireEvent.change(screen.getByLabelText('Category *'),{ target:{ value:assetDto.category_id } });
    fireEvent.change(screen.getByLabelText('Department'),{ target:{ value:deptId } });
    fireEvent.change(screen.getByLabelText('Location'),{ target:{ value:locationId } });
    fireEvent.change(screen.getByLabelText('Acquisition date *'),{ target:{ value:'2026-01-01' } });
    fireEvent.change(screen.getByLabelText('Capitalization date'),{ target:{ value:'2026-01-02' } });
    fireEvent.change(screen.getByLabelText('Purchase price *'),{ target:{ value:'1000.01' } });
    fireEvent.change(screen.getByLabelText('Freight / haulage'),{ target:{ value:'0.99' } });
    fireEvent.change(screen.getByLabelText('Useful life (months) *'),{ target:{ value:'36' } });
    expect(screen.getByText('Straight Line (SLM)')).toBeTruthy(); expect(screen.queryByText('Reducing Balance')).toBeNull();
    fireEvent.click(screen.getByRole('button',{ name:'Create draft asset' }));
    await screen.findByText(/Draft asset saved/);
    const assetRequest = requests.find(item => item.url === '/api/v1/assets/' && item.init?.method === 'POST')!;
    expect(JSON.parse(String(assetRequest.init?.body))).toMatchObject({ category_id:assetDto.category_id,department_id:deptId,location_id:locationId,purchase_cost:'1001.00',depreciation_method:'SLM' });
    fireEvent.click(screen.getByRole('button',{ name:'Record acquisition' }));
    await screen.findByText(/Acquisition saved/);
    const acquisitionRequest = requests.find(item => item.url === '/api/v1/assets/acquisitions/' && item.init?.method === 'POST')!;
    expect(JSON.parse(String(acquisitionRequest.init?.body))).toMatchObject({ asset_id:assetDto.id,purchase_price:'1000.01',freight_cost:'0.99',installation_cost:'0.00' });
    expect(screen.getByText(/NGN 1,001.00/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{ name:'Capitalize saved acquisition' }));
    await screen.findByText('Asset capitalized');
    expect(requests.some(item => item.url.includes(`/assets/acquisitions/${acquisitionId}/capitalize/`))).toBe(true);
    fireEvent.click(screen.getByRole('button',{ name:'Open asset detail' }));
    expect(navigate).toHaveBeenCalledWith(`asset-detail/${assetDto.id}`);
  });
});
