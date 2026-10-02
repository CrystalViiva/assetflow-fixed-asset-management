import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { AssetQuery } from './djangoApiBridge';
import { djangoRepository, queryClient } from './runtime';

export const assetKeys = {
  scope: (userId: number | undefined, generation: number) => ['django', userId, generation, 'assets'] as const,
};
export function useAssets(query: AssetQuery) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...assetKeys.scope(user?.id, generation), 'list', query],
    queryFn: ({ signal }) => djangoRepository.getAssets(query, signal), enabled: !!user });
}
export function useAsset(id: string) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...assetKeys.scope(user?.id, generation), 'detail', id],
    queryFn: ({ signal }) => djangoRepository.getAssetById(id, signal), enabled: !!user });
}
// F1 is read-only. Future successful mutations invalidate the owning user's asset scope.
export function invalidateAssets(userId: number, generation: number) {
  return queryClient.invalidateQueries({ queryKey: assetKeys.scope(userId, generation) });
}
