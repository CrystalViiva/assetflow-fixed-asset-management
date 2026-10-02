import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { ReferenceKind } from './assetDtos';
import { djangoRepository } from './runtime';

export const referenceKeys = { scope: (userId: number | undefined, generation: number) => ['django', userId, generation, 'references'] as const };
export function useReferences(kind: ReferenceKind) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...referenceKeys.scope(user?.id, generation), kind],
    queryFn: ({ signal }) => kind === 'categories' ? djangoRepository.getCategories(signal) : djangoRepository.getReferences(kind, signal),
    enabled: !!user, staleTime: 5 * 60_000 });
}
export function useCategories() {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: [...referenceKeys.scope(user?.id, generation), 'categories'],
    queryFn: ({ signal }) => djangoRepository.getCategories(signal), enabled: !!user, staleTime: 5 * 60_000 });
}
