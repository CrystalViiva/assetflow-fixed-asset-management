import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { dashboardRepository } from './runtime';
export const dashboardKeys = { metrics: (userId: number | undefined, generation: number) => ['django', userId, generation, 'dashboard', 'metrics'] as const };
export function useDashboardMetrics(enabled = true) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: dashboardKeys.metrics(user?.id, generation), queryFn: ({ signal }) => dashboardRepository.metrics(signal), enabled: !!user && enabled, staleTime: 30_000, refetchOnWindowFocus: true, retry: false });
}
