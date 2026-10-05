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
export function useAllAssets(query: Omit<AssetQuery, 'page'>, enabled = true) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...assetKeys.scope(user?.id, generation), 'all', query],
    queryFn: ({ signal }) => djangoRepository.getAllAssets(query, signal), enabled: !!user && enabled });
}
export function useAsset(id: string) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...assetKeys.scope(user?.id, generation), 'detail', id],
    queryFn: ({ signal }) => djangoRepository.getAssetById(id, signal), enabled: !!user });
}
// Scoped invalidation keeps successful writes from disturbing other users' cache entries.
export function invalidateAssets(userId: number, generation: number) {
  return queryClient.invalidateQueries({ queryKey: assetKeys.scope(userId, generation) });
}
