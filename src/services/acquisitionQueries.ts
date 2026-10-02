import { useMemo, useSyncExternalStore } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { assetKeys } from './assetQueries';
import { AcquisitionWorkflow } from './acquisitionWorkflow';
import { djangoRepository } from './runtime';

export const canManageAssets = (role: string | null) => role === 'ADMIN' || role === 'ASSET_MANAGER';
export const canReadAcquisitions = (role: string | null) => canManageAssets(role) || role === 'ACCOUNTANT' || role === 'DEPARTMENT_MANAGER';
export const acquisitionKeys = { scope: (userId: number | undefined, generation: number) => ['django', userId, generation, 'acquisitions'] as const };
export function useAcquisitions(query: { page: number; search?: string; asset?: string; status?: string }) {
  const { user, generation, role } = useAuth();
  return useQuery({ queryKey: [...acquisitionKeys.scope(user?.id, generation), query],
    queryFn: ({ signal }) => djangoRepository.getAcquisitions(query, signal), enabled: !!user && canReadAcquisitions(role) });
}
export function useAcquisitionWorkflow() {
  const { user, generation, isCurrent } = useAuth();
  const client = useQueryClient();
  const workflow = useMemo(() => new AcquisitionWorkflow(djangoRepository, () => isCurrent(generation), async () => {
    if (!isCurrent(generation)) return;
    await Promise.all([
      client.invalidateQueries({ queryKey: assetKeys.scope(user?.id, generation) }),
      client.invalidateQueries({ queryKey: acquisitionKeys.scope(user?.id, generation) }),
    ]);
  }), [user?.id, generation, client]);
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  const mutation = useMutation({ mutationFn: (action: () => Promise<void>) => action(), retry: false });
  return { workflow, state, run: (action: () => Promise<void>) => mutation.mutate(action) };
}
