import { QueryClient } from '@tanstack/react-query';
import { ApiClient } from './apiClient';
import { apiBase } from './config';
import { DjangoAssetRepository } from './djangoApiBridge';
import { Session } from './session';
import { DjangoDepreciationRepository } from './depreciationRepository';
import { DjangoMovementRepository } from './movementRepository';
import { DjangoMaintenanceRepository } from './maintenanceRepository';
import { DjangoDisposalRepository } from './disposalRepository';

export const queryClient = new QueryClient({ defaultOptions: { queries: {
  staleTime: 30_000, gcTime: 5 * 60_000, retry: false, refetchOnWindowFocus: true,
}, mutations: { retry: false } } });
export const apiClient = new ApiClient(apiBase);
// Lazy storage access also works when browser privacy settings throw on access.
export const session = new Session(apiClient, {
  getItem: key => window.sessionStorage.getItem(key),
  setItem: (key, value) => window.sessionStorage.setItem(key, value),
  removeItem: key => window.sessionStorage.removeItem(key),
}, () => { queryClient.clear(); });
export const djangoRepository = new DjangoAssetRepository(apiClient);
export const depreciationRepository = new DjangoDepreciationRepository(apiClient);
export const movementRepository = new DjangoMovementRepository(apiClient);
export const maintenanceRepository = new DjangoMaintenanceRepository(apiClient);
export const disposalRepository = new DjangoDisposalRepository(apiClient);
