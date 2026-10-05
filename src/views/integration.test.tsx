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
import { BackendAssignmentsView } from './BackendAssignmentsView';
import { BackendTransfersView } from './BackendTransfersView';
import { LoginView } from './LoginView';
import { defaultAssetQuery } from '../services/djangoApiBridge';
import { useMovementAction } from '../services/movementMutations';
import { BackendVerificationView } from './BackendVerificationView';

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
    if (url.includes('/assets/maintenance-plans/') || url.includes('/assets/work-orders/') || url.includes('/assets/maintenance-costs/') || url.includes('/assets/maintenance-records/')) return json(emptyPage);
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
describe('F7 physical verification screen',()=>{
 it('renders database-derived campaign progress and keeps observation history empty when Django returns none',async()=>{
  const c=await authenticated('ACCOUNTANT');const departmentId='55555555-5555-4555-8555-555555555555';const campaign={id:'66666666-6666-4666-8666-666666666666',organization_id:assetDto.organization_id,name:'Quarterly stocktake',description:'',status:'OPEN',scope_type:'DEPARTMENT',department_id:departmentId,location_id:null,start_date:'2026-04-01',due_date:null,opened_at:'2026-04-01T10:00:00Z',completed_at:null,created_by_email:'manager@example.test',expected_asset_count:8,verified_asset_count:3,unverified_asset_count:5,exception_count:2,resolved_exception_count:1,verification_percentage:'37.50',created_at:'2026-04-01T09:00:00Z',updated_at:'2026-04-01T10:00:00Z'};
  c.fetcher.mockImplementation(async input=>{const url=String(input);if(url.includes('/verification/campaigns/'))return json({count:1,next:null,previous:null,results:[campaign]});if(url.includes('/verification/records/'))return json(emptyPage);if(url.includes('/verification/exceptions/'))return json(emptyPage);if(url.includes('/departments/'))return json({...emptyPage,results:[{id:departmentId,organization_id:assetDto.organization_id,name:'Operations',code:'OPS',is_active:true}],count:1});if(url.includes('/locations/'))return json(emptyPage);return json(emptyPage);});
  render(frame(c.session,c.client,<BackendVerificationView/>));expect(await screen.findByText('Quarterly stocktake')).toBeTruthy();expect(screen.getByText(/Coverage 37.50% · 3\/8 registered assets · 5 not observed · 2 exceptions \(1 resolved\)/)).toBeTruthy();expect(screen.queryByText('1,284')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Open observations'}));expect(await screen.findByText('No physical observations recorded.')).toBeTruthy();expect(c.fetcher.mock.calls.some(call=>String(call[0]).includes('/verification/records/?'))).toBe(true);
 });
});
describe('real asset detail and cache security', () => {
  it('renders loading then real overview, null fields, real maintenance and only unsupported pending tabs', async () => {
    const c = await authenticated(); const pending = deferred<Response>();
    backendData(c.fetcher, url => url.includes(`/assets/${assetDto.id}/`) ? pending.promise : json(emptyPage));
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={() => {}} />));
    expect(screen.getByRole('status').textContent).toContain('Loading asset details');
    await act(async () => { pending.resolve(json(assetDto)); });
    expect(await screen.findByRole('heading',{ name:'REAL-001 - Office generator' })).toBeTruthy();
    const tabs = screen.getAllByRole('button',{ name:/Integration pending/ }); expect(tabs).toHaveLength(2);
    for (const tab of tabs) expect(tab.hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button',{ name:'Maintenance' }));
    expect(await screen.findByText('No maintenance plans.')).toBeTruthy();
  });
  it('loads real assignment and transfer history tabs from their own backend resources', async () => {
    const c = await authenticated('ASSET_MANAGER');
    const at='2026-01-01T10:00:00Z';
    const assignment={ id:'11111111-1111-4111-8111-111111111111',organization_id:assetDto.organization_id,asset_id:assetDto.id,asset_tag:assetDto.asset_tag,asset_name:assetDto.name,
      assigned_to_id:7,assigned_to_email:'custodian@example.test',department_id:assetDto.department_id,department_name:assetDto.department_name,location_id:assetDto.location_id,location_name:assetDto.location_name,
      assigned_at:at,returned_at:null,returned_by_email:null,notes:'Custody record',created_by_email:'manager@example.test',created_at:at,updated_at:at };
    const transfer={ id:'22222222-2222-4222-8222-222222222222',organization_id:assetDto.organization_id,asset_id:assetDto.id,asset_tag:assetDto.asset_tag,asset_name:assetDto.name,
      from_department_id:assetDto.department_id,from_department_name:assetDto.department_name,from_location_id:assetDto.location_id,from_location_name:assetDto.location_name,
      to_department_id:'33333333-3333-4333-8333-333333333333',to_department_name:'Finance',to_location_id:'44444444-4444-4444-8444-444444444444',to_location_name:'Head Office',
      requested_by_email:'manager@example.test',approved_by_email:null,completed_by_email:null,rejected_by_email:null,cancelled_by_email:null,requested_at:at,approved_at:null,completed_at:null,rejected_at:null,cancelled_at:null,status:'REQUESTED',reason:'Relocation',notes:'' };
    c.fetcher.mockImplementation(async input => { const url=String(input); if(url===`/api/v1/assets/${assetDto.id}/`)return json(assetDto);if(url.includes('/assets/assignments/'))return json({count:1,next:null,previous:null,results:[assignment]});if(url.includes('/assets/transfers/'))return json({count:1,next:null,previous:null,results:[transfer]});if(url.includes('/assets/acquisitions/'))return json(emptyPage);return json(emptyPage); });
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={()=>{}} />));
    await screen.findByRole('heading',{name:'REAL-001 - Office generator'});
    fireEvent.click(screen.getByRole('button',{name:'Assignments'}));
    expect(await screen.findByText('custodian@example.test')).toBeTruthy();expect(screen.getByText('Custody record')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'Transfers'}));
    expect(await screen.findByText(/Finance \/ Head Office/)).toBeTruthy();expect(screen.getByText('Relocation')).toBeTruthy();
    expect(c.fetcher.mock.calls.some(([url])=>String(url).includes('/assets/assignments/'))).toBe(true);
    expect(c.fetcher.mock.calls.some(([url])=>String(url).includes('/assets/transfers/'))).toBe(true);
    expect(screen.queryByText(/AST-000002/)).toBeNull();
  });
  it('loads authoritative verification history with one asset-filtered request from the detail tab',async()=>{
    const c=await authenticated('ACCOUNTANT');const record={id:'77777777-7777-4777-8777-777777777777',organization_id:assetDto.organization_id,campaign_id:'88888888-8888-4888-8888-888888888888',asset_id:assetDto.id,asset_tag:assetDto.asset_tag,verified_at:'2026-04-01T12:00:00Z',verified_by_email:'manager@example.test',result:'LOCATION_MISMATCH',observed_location_id:'99999999-9999-4999-8999-999999999999',observed_department_id:assetDto.department_id,observed_custodian_id:null,observed_condition:'GOOD',observed_asset_tag:'OTHER-TAG',observed_description:'Seen at another site',notes:'Counted during check',exceptions:[{id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',exception_type:'LOCATION_MISMATCH',severity:'MEDIUM',status:'OPEN',description:'Observed location differs from the asset register.'}],created_at:'2026-04-01T12:00:00Z',updated_at:'2026-04-01T12:00:00Z'};
    c.fetcher.mockImplementation(async input=>{const url=String(input);if(url===`/api/v1/assets/${assetDto.id}/`)return json(assetDto);if(url.includes('/verification/records/')){expect(url).toContain(`asset=${assetDto.id}`);return json({count:1,next:null,previous:null,results:[record]});}return json(emptyPage);});
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={()=>{}}/>));await screen.findByRole('heading',{name:'REAL-001 - Office generator'});expect(c.fetcher.mock.calls.some(call=>String(call[0]).includes('/verification/records/'))).toBe(false);fireEvent.click(screen.getByRole('button',{name:'Verification'}));expect(await screen.findByText(/LOCATION_MISMATCH · observed/)).toBeTruthy();expect(screen.getByText(/Seen at another site/)).toBeTruthy();expect(c.fetcher.mock.calls.filter(call=>String(call[0]).includes('/verification/records/'))).toHaveLength(1);
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

describe('real custody operations screen',()=>{
  it('loads paginated tenant references and real active assignment records',async()=>{
    const c=await authenticated('ASSET_MANAGER');const at='2026-01-01T10:00:00Z';const assignmentId='11111111-1111-4111-8111-111111111111';
    const assignment={id:assignmentId,organization_id:assetDto.organization_id,asset_id:assetDto.id,asset_tag:'REAL-001',asset_name:'Office generator',assigned_to_id:7,assigned_to_email:'custodian@example.test',department_id:null,department_name:null,location_id:null,location_name:null,assigned_at:at,returned_at:null,returned_by_email:null,notes:'Active custody',created_by_email:'manager@example.test',created_at:at,updated_at:at};
    c.fetcher.mockImplementation(async input=>{const url=String(input);if(url.includes('/assets/assignments/'))return json({count:1,next:null,previous:null,results:[assignment]});if(url.includes('/custodians/'))return json({count:1,next:null,previous:null,results:[{id:7,email:'custodian@example.test',role:'EMPLOYEE',department_id:null,department_name:null}]});if(url.includes('/assets/'))return json(emptyPage);throw new Error(`Unexpected ${url}`);});
    const select=vi.fn();render(frame(c.session,c.client,<BackendAssignmentsView onNavigate={()=>{}} onSelectAsset={select}/>));
    expect(await screen.findByText('custodian@example.test')).toBeTruthy();expect(screen.getByText('Active',{selector:'td'})).toBeTruthy();
    expect(screen.getByRole('button',{name:'Assign custody'}).hasAttribute('disabled')).toBe(true);
    expect(c.fetcher.mock.calls.some(([url])=>String(url).includes('/custodians/'))).toBe(true);
  });
  it('creates and returns custody through backend actions without sending placement fields',async()=>{
    const c=await authenticated('ASSET_MANAGER');const at='2026-01-01T10:00:00Z';const id='11111111-1111-4111-8111-111111111111';let created=false;let returned=false;
    const assignment=()=>({id,organization_id:assetDto.organization_id,asset_id:assetDto.id,asset_tag:'REAL-001',asset_name:'Office generator',assigned_to_id:7,assigned_to_email:'custodian@example.test',department_id:assetDto.department_id,department_name:assetDto.department_name,location_id:assetDto.location_id,location_name:assetDto.location_name,assigned_at:at,returned_at:returned?at:null,returned_by_email:returned?'manager@example.test':null,notes:'UI custody workflow',created_by_email:'manager@example.test',created_at:at,updated_at:at});
    c.fetcher.mockImplementation(async(input,init)=>{const url=String(input);if(url.includes('/assets/assignments/')&&url.endsWith('/return/')){returned=true;return json(assignment());}if(url.includes('/assets/assignments/')&&init?.method==='POST'){expect(JSON.parse(String(init.body))).toEqual({asset_id:assetDto.id,assigned_to_id:7,notes:'UI custody workflow'});created=true;return json(assignment());}if(url.includes('/assets/assignments/')){const active=url.includes('active=true');return json({count:active?Number(created&&!returned):Number(created&&returned),next:null,previous:null,results:active?created&&!returned?[assignment()]:[]:created&&returned?[assignment()]:[]});}if(url.includes('/custodians/'))return json({count:1,next:null,previous:null,results:[{id:7,email:'custodian@example.test',role:'EMPLOYEE',department_id:null,department_name:null}]});if(url.includes('/assets/')&&url.includes('page_size=100'))return json({count:1,next:null,previous:null,results:[assetDto]});throw new Error(`Unexpected ${url}`);});
    render(frame(c.session,c.client,<BackendAssignmentsView onNavigate={()=>{}} onSelectAsset={()=>{}}/>));
    expect(await screen.findByRole('option',{name:/REAL-001/})).toBeTruthy();expect(await screen.findByRole('option',{name:/custodian@example.test/})).toBeTruthy();fireEvent.change(screen.getByLabelText('Asset'),{target:{value:assetDto.id}});fireEvent.change(screen.getByLabelText('Custodian'),{target:{value:'7'}});fireEvent.change(screen.getByLabelText('Notes'),{target:{value:'UI custody workflow'}});expect(screen.getByRole('button',{name:'Assign custody'}).hasAttribute('disabled')).toBe(false);fireEvent.click(screen.getByRole('button',{name:'Assign custody'}));
    await waitFor(()=>expect(c.fetcher.mock.calls.some(([url,init])=>String(url).includes('/assets/assignments/')&&init?.method==='POST')).toBe(true));expect(await screen.findByText('Custody assignment saved. Asset placement is unchanged.')).toBeTruthy();
    fireEvent.click(await screen.findByRole('button',{name:'Return'}));expect(await screen.findByText('Assignment returned; history retained and asset placement unchanged.')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'History'}));expect(await screen.findByText('UI custody workflow')).toBeTruthy();
  });
});

describe('movement mutation session safety',()=>{
  it('does not apply an old-session result to the cache after logout',async()=>{
    const c=await authenticated('ASSET_MANAGER');let finish!:()=>void;let mutation:Promise<unknown>|undefined;
    const operation=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve;}));const invalidate=vi.spyOn(c.client,'invalidateQueries');
    function Harness(){const action=useMovementAction('assignments');return <button onClick={()=>{mutation=action.run(operation);void mutation.catch(()=>{});}}>Run movement</button>;}
    render(frame(c.session,c.client,<Harness/>));fireEvent.click(screen.getByRole('button',{name:'Run movement'}));await waitFor(()=>expect(operation).toHaveBeenCalledOnce());
    c.session.logout();finish();await expect(mutation).rejects.toMatchObject({kind:'authentication'});expect(invalidate).not.toHaveBeenCalled();
  });
});

describe('real transfer operations screen',()=>{
  it('loads backend history and completes through the transition route before refreshing placement queries',async()=>{
    const c=await authenticated('ASSET_MANAGER');const at='2026-01-01T10:00:00Z';const id='22222222-2222-4222-8222-222222222222';let status='APPROVED';let placementReads=0;
    const makeTransfer=()=>({id,organization_id:assetDto.organization_id,asset_id:assetDto.id,asset_tag:'REAL-001',asset_name:'Office generator',from_department_id:'55555555-5555-4555-8555-555555555555',from_department_name:'Operations',from_location_id:'66666666-6666-4666-8666-666666666666',from_location_name:'Main Plant',to_department_id:'33333333-3333-4333-8333-333333333333',to_department_name:'Finance',to_location_id:'44444444-4444-4444-8444-444444444444',to_location_name:'Head Office',requested_by_email:'manager@example.test',approved_by_email:'manager@example.test',completed_by_email:status==='COMPLETED'?'manager@example.test':null,rejected_by_email:null,cancelled_by_email:null,requested_at:at,approved_at:at,completed_at:status==='COMPLETED'?at:null,rejected_at:null,cancelled_at:null,status,reason:'Relocation',notes:''});
    c.fetcher.mockImplementation(async(input,init)=>{const url=String(input);if(url.includes('/assets/transfers/')&&url.endsWith('/complete/')&&init?.method==='POST'){status='COMPLETED';return json(makeTransfer());}if(url.includes('/assets/transfers/'))return json({count:1,next:null,previous:null,results:[makeTransfer()]});if(url==='/api/v1/assets/'||url.startsWith('/api/v1/assets/?')){placementReads++;return json(emptyPage);}if(url.includes('/departments/')||url.includes('/locations/'))return json(emptyPage);throw new Error(`Unexpected ${url}`);});
    render(frame(c.session,c.client,<BackendTransfersView onNavigate={()=>{}} onSelectAsset={()=>{}}/>));
    expect(await screen.findByRole('button',{name:/REAL-001.*Office generator/})).toBeTruthy();expect(screen.getByText(/Operations \/ Main Plant/)).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Complete transfer'}));
    await waitFor(()=>expect(c.fetcher.mock.calls.some(([url,init])=>String(url).endsWith('/complete/')&&init?.method==='POST')).toBe(true));expect(await screen.findByText('Transfer completed; authoritative placement has been refreshed.')).toBeTruthy();expect(placementReads).toBeGreaterThan(1);expect(screen.getByText('COMPLETED')).toBeTruthy();
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
