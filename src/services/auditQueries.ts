import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { AuditFilters } from './auditRepository';
import { auditRepository } from './runtime';

export const auditKeys = {
  scope: (userId: number | undefined, generation: number) => ['django', userId, generation, 'audit'] as const,
  events: (userId: number | undefined, generation: number, filters: AuditFilters) => [...auditKeys.scope(userId, generation), 'events', filters] as const,
};
export function useAuditEvents(filters: AuditFilters, enabled = true) {
  const { user, generation } = useAuth();
  return useQuery({ queryKey: auditKeys.events(user?.id, generation, filters),
    queryFn: ({ signal }) => auditRepository.events(filters, signal), enabled: !!user && enabled });
}
