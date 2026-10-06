import { QueryClient } from '@tanstack/react-query';
import { ApiClient } from './apiClient';
import { apiBase } from './config';
import { Session } from './session';

export const queryClient = new QueryClient({ defaultOptions: { queries: {
  staleTime: 30_000, gcTime: 5 * 60_000, retry: false, refetchOnWindowFocus: true,
}, mutations: { retry: false } } });
export const apiClient = new ApiClient(apiBase);

// Keep authentication bootstrap independent from domain repositories and lazy screens.
export const session = new Session(apiClient, {
  getItem: key => window.sessionStorage.getItem(key),
  setItem: (key, value) => window.sessionStorage.setItem(key, value),
  removeItem: key => window.sessionStorage.removeItem(key),
}, () => { queryClient.clear(); });
