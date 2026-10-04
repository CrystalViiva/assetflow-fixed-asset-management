import { QueryClient, useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { assetKeys } from './assetQueries';
import { depreciationRepository } from './runtime';

export const depreciationKeys = {
  scope: (userId: number | undefined, generation: number) => ['django', userId, generation, 'depreciation'] as const,
  periods: (userId: number | undefined, generation: number) => [...depreciationKeys.scope(userId, generation), 'periods'] as const,
  schedules: (userId: number | undefined, generation: number) => [...depreciationKeys.scope(userId, generation), 'schedules'] as const,
  entries: (userId: number | undefined, generation: number, assetId?: string, periodId?: string) => [...depreciationKeys.scope(userId, generation), 'entries', assetId ?? '', periodId ?? ''] as const,
};
export function useAccountingPeriods() {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: depreciationKeys.periods(user?.id, generation), queryFn: ({ signal }) => depreciationRepository.getPeriods(signal), enabled: !!user });
}
export function useDepreciationSchedules(enabled = true) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: depreciationKeys.schedules(user?.id, generation), queryFn: ({ signal }) => depreciationRepository.getSchedules(signal), enabled: !!user && enabled });
}
export function useDepreciationEntries(assetId?: string, periodId?: string, enabled = true) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: depreciationKeys.entries(user?.id, generation, assetId, periodId), queryFn: ({ signal }) => depreciationRepository.getEntries({ asset: assetId, period: periodId }, signal), enabled: !!user && enabled });
}
export async function invalidateDepreciation(client: QueryClient, userId: number | undefined, generation: number, assetId?: string) {
  await Promise.all([
    client.invalidateQueries({ queryKey: depreciationKeys.scope(userId, generation) }),
    client.invalidateQueries({ queryKey: assetKeys.scope(userId, generation) }),
    ...(assetId ? [client.invalidateQueries({ queryKey: depreciationKeys.entries(userId, generation, assetId) })] : []),
  ]);
}
