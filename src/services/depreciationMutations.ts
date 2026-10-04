import { useMemo, useSyncExternalStore } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { depreciationRepository } from './runtime';
import { DepreciationWorkflow } from './depreciationWorkflow';
import { invalidateDepreciation } from './depreciationQueries';

export function useDepreciationWorkflow(assetId?: string, periodId?: string) {
  const { user, generation, isCurrent } = useAuth();
  const client = useQueryClient();
  const workflow = useMemo(() => new DepreciationWorkflow(depreciationRepository, () => isCurrent(generation), changedAssetId => invalidateDepreciation(client, user?.id, generation, changedAssetId)), [user?.id, generation, client, assetId, periodId]);
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  const mutation = useMutation({ mutationFn: ([assetId, periodId]: [string, string]) => workflow.post(assetId, periodId), retry: false });
  const reconcileMutation = useMutation({ mutationFn: ([assetId, periodId]: [string, string]) => workflow.reconcile(assetId, periodId), retry: false });
  return { workflow, state, post: (assetId: string, periodId: string) => mutation.mutate([assetId, periodId]), reconcile: (assetId: string, periodId: string) => reconcileMutation.mutate([assetId, periodId]), mutationPending: mutation.isPending || reconcileMutation.isPending };
}
