import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './AuthProvider';
import { DjangoRoutes, MockRoutes, safeReturnRoute } from './ApplicationRoot';
import { Session } from '../services/session';
import { ApiClient } from '../services/apiClient';
import { json } from '../test/fixtures';

afterEach(() => { window.location.hash = ''; sessionStorage.clear(); });

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const fetcher = vi.fn<typeof fetch>();
  const session = new Session(new ApiClient('/api/v1', fetcher), sessionStorage, () => client.clear());
  return { client, fetcher, session };
}

describe('F14 public/private routing', () => {
  it.each([
    ['dashboard', 'dashboard'], ['asset-detail/c942f6c8-581c-430d-b234-b6853a4e7c94', 'asset-detail/c942f6c8-581c-430d-b234-b6853a4e7c94'],
  ])('accepts the internal route %s', (raw, route) => expect(safeReturnRoute(raw)).toBe(route));

  it.each(['https://example.test', '//example.test', 'javascript:alert(1)', 'data:text/html,x', 'login', 'dashboard?next=login', '../dashboard'])('rejects unsafe return route %s', raw => expect(safeReturnRoute(raw)).toBeNull());

  it('renders the public landing without calling protected APIs', async () => {
    const { client, fetcher, session } = setup();
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByRole('heading', { name: /know your assets.*control their value/i })).toBeTruthy();
    await waitFor(() => expect(session.getSnapshot().initializing).toBe(false));
    expect(fetcher).not.toHaveBeenCalled();
    expect(fetcher.mock.calls.some(call => String(call[0]).includes('/dashboard/'))).toBe(false);
  });

  it('keeps direct homepage sections and unknown Django routes out of auth redirects', async () => {
    window.location.hash = '#/section-pricing';
    const publicSetup = setup();
    const publicView = render(<QueryClientProvider client={publicSetup.client}><AuthProvider value={publicSetup.session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByRole('heading', { name: /know your assets.*control their value/i })).toBeTruthy();
    expect(publicSetup.fetcher).not.toHaveBeenCalled();
    publicView.unmount();

    window.location.hash = '#/not-a-real-route';
    const unknown = setup();
    render(<QueryClientProvider client={unknown.client}><AuthProvider value={unknown.session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByRole('heading', { name: /this page.*here/i })).toBeTruthy();
    expect(window.location.hash).toBe('#/not-a-real-route');
  });

  it('keeps mock login, trial onboarding and unknown routes honest and distinct', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    const renderMock = () => render(<QueryClientProvider client={client}><MockRoutes /></QueryClientProvider>);
    window.location.hash = '#/login?next=dashboard';
    const login = renderMock();
    expect(await screen.findByRole('heading', { name: /sign in to your assetflow workspace/i })).toBeTruthy();
    expect(screen.queryByLabelText('Password')).toBeNull();
    login.unmount();

    window.location.hash = '#/signup';
    const signup = renderMock();
    expect(await screen.findByRole('heading', { name: /live trial needs the configured assetflow service/i })).toBeTruthy();
    expect(screen.getAllByRole('link', { name: /request a demo/i }).some(link => link.getAttribute('href') === '#request-demo')).toBe(true);
    signup.unmount();

    window.location.hash = '#/not-a-route';
    renderMock();
    expect(await screen.findByRole('heading', { name: /this page.*here/i })).toBeTruthy();
    expect(screen.getByRole('link', { name: /return to assetflow/i }).getAttribute('href')).toBe('#/');
  });

  it('redirects a protected route to sign in with a safe intended route and never mounts its data view', async () => {
    window.location.hash = '#dashboard';
    const { client, fetcher, session } = setup();
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByLabelText('Email')).toBeTruthy();
    await waitFor(() => expect(window.location.hash).toBe('#login?next=dashboard'));
    expect(fetcher.mock.calls.some(call => String(call[0]).includes('/dashboard/metrics/'))).toBe(false);
  });

  it('sends an already authenticated visit to login back to its validated destination', async () => {
    const { client, fetcher, session } = setup();
    await session.initialize();
    fetcher.mockResolvedValueOnce(json({ access: 'temporary-access', refresh: 'temporary-refresh' })).mockResolvedValueOnce(json({ id: 8, email: 'admin@example.test', role: 'ADMIN' }));
    await session.login('admin@example.test', 'temporary-password');
    window.location.hash = '#login?next=all-assets';
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    await waitFor(() => expect(window.location.hash).toBe('#all-assets'));
  });

  it('keeps the public homepage and its section navigation available to authenticated users', async () => {
    const { client, fetcher, session } = setup();
    await session.initialize();
    fetcher.mockResolvedValueOnce(json({ access: 'temporary-access', refresh: 'temporary-refresh' })).mockResolvedValueOnce(json({ id: 8, email: 'admin@example.test', role: 'ADMIN' }));
    await session.login('admin@example.test', 'temporary-password');
    window.location.hash = '#/';
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByRole('heading', { name: /know your assets.*control their value/i })).toBeTruthy();
    await userEvent.setup().click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: 'Features' }));
    await waitFor(() => expect(window.location.hash).toBe('#section-features'));
    expect(screen.getByRole('heading', { name: /know your assets.*control their value/i })).toBeTruthy();
  });

  it('returns a successful sign in to the requested internal route', async () => {
    window.location.hash = '#login?next=all-assets';
    const { client, fetcher, session } = setup();
    await session.initialize();
    fetcher.mockResolvedValueOnce(json({ access: 'temporary-access', refresh: 'temporary-refresh' })).mockResolvedValueOnce(json({ id: 8, email: 'admin@example.test', role: 'ADMIN' }));
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Email'), 'admin@example.test');
    await user.type(screen.getByLabelText('Password'), 'temporary-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(window.location.hash).toBe('#all-assets'));
  });

  it('discards a malicious login next value and uses dashboard as the fallback', async () => {
    window.location.hash = '#login?next=https%3A%2F%2Fevil.test';
    const { client, fetcher, session } = setup();
    await session.initialize();
    fetcher.mockReset();
    fetcher.mockResolvedValueOnce(json({ access: 'temporary-access', refresh: 'temporary-refresh' })).mockResolvedValueOnce(json({ id: 8, email: 'admin@example.test', role: 'ADMIN' }));
    render(<QueryClientProvider client={client}><AuthProvider value={session}><DjangoRoutes /></AuthProvider></QueryClientProvider>);
    expect(await screen.findByLabelText('Email')).toBeTruthy();
    expect(safeReturnRoute(new URLSearchParams(window.location.hash.split('?')[1]).get('next'))).toBeNull();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email'), 'admin@example.test');
    await user.type(screen.getByLabelText('Password'), 'temporary-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(window.location.hash).toBe('#dashboard'));
    expect(fetcher.mock.calls.some(call => String(call[0]).startsWith('https://evil.test'))).toBe(false);
  });
});
