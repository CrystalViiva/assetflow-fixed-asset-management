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
import { LoginView } from './LoginView';
import { defaultAssetQuery } from '../services/djangoApiBridge';

afterEach(() => vi.unstubAllGlobals());
function frame(session: Session, client: QueryClient, children: ReactNode) {
  return <QueryClientProvider client={client}><AuthProvider value={session}>{children}</AuthProvider></QueryClientProvider>;
}
async function authenticated() {
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false,gcTime:0 } } });
  const session = new Session(apiClient,sessionStorage,() => client.clear());
  const fetcher = vi.fn<typeof fetch>(); vi.stubGlobal('fetch',fetcher);
  await session.initialize();
  fetcher.mockResolvedValueOnce(json({ access:'test-access-1',refresh:'test-refresh-1' })).mockResolvedValueOnce(json(identity));
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
    const c = await authenticated(); const pending = deferred<Response>(); c.fetcher.mockReturnValue(pending.promise);
    const select = vi.fn(); render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={select} />));
    expect(screen.getByRole('status').textContent).toContain('Loading assets');
    await act(async () => { pending.resolve(json({ count:1,next:null,previous:null,results:[assetDto] })); });
    fireEvent.click(await screen.findByRole('button',{ name:'REAL-001' })); expect(select).toHaveBeenCalledWith(assetDto.id);
    expect(screen.getByText('999,999,999,999,999,999.99')).toBeTruthy(); expect(screen.queryByText('AST-000002')).toBeNull();
  });
  it('renders empty results', async () => {
    const c = await authenticated(); c.fetcher.mockResolvedValue(json({ count:0,next:null,previous:null,results:[] }));
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    expect(await screen.findByText('No assets match these filters.')).toBeTruthy(); expect(screen.getByText('0 assets · Page 1 of 1')).toBeTruthy();
  });
  it.each([403,500])('renders HTTP %s without mock fallback', async status => {
    const c = await authenticated(); c.fetcher.mockResolvedValue(json({},status));
    render(frame(c.session,c.client,<BackendAssetRegister globalSearch="" onSelectAsset={() => {}} />));
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(screen.queryByText('AST-000002')).toBeNull();
  });
  it('paginates and resets page for search and filter changes', async () => {
    const c = await authenticated();
    c.fetcher.mockImplementation(async url => { const page = new URL(String(url),'http://localhost').searchParams.get('page');
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
    c.fetcher.mockImplementation(async url => String(url).includes('search=old') ? slow.promise
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
    const c = await authenticated(); const pending = deferred<Response>(); c.fetcher.mockReturnValue(pending.promise);
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={() => {}} />));
    expect(screen.getByRole('status').textContent).toContain('Loading asset details');
    await act(async () => { pending.resolve(json(assetDto)); });
    expect(await screen.findByRole('heading',{ name:'REAL-001 — Office generator' })).toBeTruthy();
    const tabs = screen.getAllByRole('button',{ name:/Integration pending/ }); expect(tabs).toHaveLength(6);
    for (const tab of tabs) expect(tab.hasAttribute('disabled')).toBe(true);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0); expect(c.fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([404,403,500])('handles detail HTTP %s', async status => {
    const c = await authenticated(); c.fetcher.mockResolvedValue(json({},status));
    render(frame(c.session,c.client,<BackendAssetDetail assetId={assetDto.id} onNavigate={() => {}} />));
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(screen.queryByText('Office generator')).toBeNull();
  });
  it('clears cached user A assets and renders no A data when user B logs in', async () => {
    const c = await authenticated();
    c.fetcher.mockResolvedValue(json({ count:1,next:null,previous:null,results:[{ ...assetDto,name:'User A private asset' }] }));
    function Boundary() { const auth = useAuth(); return auth.authenticated ? <BackendAssetRegister key={auth.generation} globalSearch="" onSelectAsset={() => {}} /> : <p>Signed out</p>; }
    render(frame(c.session,c.client,<Boundary />)); await screen.findByText('User A private asset');
    act(() => c.session.logout()); expect(c.client.getQueryCache().getAll()).toHaveLength(0);
    expect(screen.queryByText('User A private asset')).toBeNull(); expect(sessionStorage.getItem(REFRESH_KEY)).toBeNull();
    c.fetcher.mockReset(); c.fetcher.mockResolvedValueOnce(json({ access:'test-access-b',refresh:'test-refresh-b' })).mockResolvedValueOnce(json({ ...identity,id:2,email:'two@example.test' }))
      .mockResolvedValue(json({ count:0,next:null,previous:null,results:[] }));
    await act(async () => { await c.session.login('two@example.test','test-password'); });
    expect(screen.queryByText('User A private asset')).toBeNull(); await screen.findByText('No assets match these filters.');
    expect(c.session.getSnapshot().user?.id).toBe(2);
  });
});
