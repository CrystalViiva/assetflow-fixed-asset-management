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

afterEach(() => { vi.unstubAllGlobals(); window.location.hash = ''; });
async function renderRealApp() {
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false } } });
  const session = new Session(apiClient,sessionStorage,() => client.clear());
  const fetcher = vi.fn<typeof fetch>(); vi.stubGlobal('fetch',fetcher);
  await session.initialize(); fetcher.mockResolvedValueOnce(json({ access:'test-access',refresh:'test-refresh' })).mockResolvedValueOnce(json(identity));
  await session.login(identity.email,'test-password'); fetcher.mockReset();
  fetcher.mockResolvedValue(json({ count:1,next:null,previous:null,results:[assetDto] }));
  vi.spyOn(window,'scrollTo').mockImplementation(() => {});
  render(<QueryClientProvider client={client}><AuthProvider value={session}><AuthenticatedApplication /></AuthProvider></QueryClientProvider>);
  return { session,client,fetcher };
}
it('real-mode shell shows real identity, no mock alerts/actions, and logs out', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator');
  expect(screen.getByText(identity.email)).toBeTruthy(); expect(screen.queryByText('Babajide Adeleke')).toBeNull();
  for (const text of ['1,284','4 pending','2 overdue','Lagos Corporate Facility']) expect(screen.queryByText(text)).toBeNull();
  expect(screen.queryByRole('button',{ name:'Actions' })).toBeNull(); expect(screen.queryByTitle('Notifications')).toBeNull();
  fireEvent.click(screen.getByRole('button',{ name:'Sign out' }));
  expect(await screen.findByRole('button',{ name:'Sign in' })).toBeTruthy(); expect(c.client.getQueryCache().getAll()).toHaveLength(0);
});
it('real-mode unintegrated routes render pending instead of demo screens', async () => {
  await renderRealApp(); await screen.findByText('Office generator');
  fireEvent.click(screen.getByRole('button',{ name:'Dashboard' }));
  expect(await screen.findByRole('heading',{ name:'Integration pending' })).toBeTruthy();
  expect(screen.queryByText('Office generator')).toBeNull();
});
it('real-mode asset UUID opens only the real detail overview', async () => {
  const c = await renderRealApp(); await screen.findByText('Office generator'); c.fetcher.mockResolvedValue(json(assetDto));
  fireEvent.click(screen.getByRole('button',{ name:'REAL-001' }));
  expect(await screen.findByRole('heading',{ name:'REAL-001 — Office generator' })).toBeTruthy();
  expect(window.location.hash).toBe(`#asset-detail/${assetDto.id}`);
  expect(screen.getAllByRole('button',{ name:/Integration pending/ })).toHaveLength(6);
  act(() => c.session.logout());
});
it('guards the mock repository from accidental use in Django mode', async () => {
  const repository = new MockAssetRepository();
  await expect(repository.getAssets()).rejects.toThrow('Mock data is unavailable');
  await expect(repository.getUsers()).rejects.toThrow('Mock data is unavailable');
  await expect(repository.resetToDefaultData()).rejects.toThrow('Mock data is unavailable');
});
