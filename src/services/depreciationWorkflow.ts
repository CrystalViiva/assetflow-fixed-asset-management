import { ApiError } from './apiError';
import { DepreciationEntryRecord } from './depreciationDtos';
import { DjangoDepreciationRepository } from './depreciationRepository';

export interface PostingState { busy: boolean; uncertain: boolean; entry: DepreciationEntryRecord | null; error: unknown; notice: string }
type PostingRepository = Pick<DjangoDepreciationRepository, 'post' | 'getEntries'>;
/** Prevents repeat clicks and reconciles every unclear posting result against the ledger. */
export class DepreciationWorkflow {
  private static readonly inFlight = new Map<string, Promise<void>>();
  private state: PostingState = { busy: false, uncertain: false, entry: null, error: null, notice: '' };
  private listeners = new Set<() => void>();
  constructor(private readonly repository: PostingRepository, private readonly isCurrent: () => boolean, private readonly invalidate: (assetId: string) => Promise<unknown>) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  private set(update: Partial<PostingState>) { if (!this.isCurrent()) return; this.state = { ...this.state, ...update }; this.listeners.forEach(listener => listener()); }
  post = async (assetId: string, periodId: string) => {
    if (!this.isCurrent() || this.state.busy || this.state.uncertain || this.state.entry) return;
    const key = `${assetId}:${periodId}`;
    const ongoing = DepreciationWorkflow.inFlight.get(key);
    if (ongoing) {
      this.set({ busy:true, uncertain:true, notice:'A posting request for this asset and period is already in progress. Waiting to reconcile its ledger result.' });
      await ongoing;
      if (!this.isCurrent()) return;
      this.set({ busy:false });
      await this.reconcile(assetId,periodId);
      return;
    }
    this.set({ busy: true, error: null, notice: '' });
    const operation = this.executePost(assetId,periodId);
    DepreciationWorkflow.inFlight.set(key,operation);
    try { await operation; }
    finally { if (DepreciationWorkflow.inFlight.get(key) === operation) DepreciationWorkflow.inFlight.delete(key); }
  };
  private async executePost(assetId: string, periodId: string) {
    try {
      const entry = await this.repository.post(assetId, periodId);
      if (!this.isCurrent()) return;
      if (entry.assetId !== assetId || entry.periodId !== periodId) throw new ApiError('contract', 'The posting response did not match the selected asset and period.');
      this.set({ entry, notice: 'Depreciation is posted. Ledger and asset balances are being refreshed.' });
      await this.invalidate(assetId);
    } catch (error) {
      if (!this.isCurrent()) return;
      this.set({ uncertain: true, notice: 'The posting response was not confirmed. Checking the posted ledger before enabling another attempt.' });
      this.set({ busy: false });
      await this.reconcile(assetId, periodId, error);
    } finally { this.set({ busy: false }); }
  }
  reconcile = async (assetId: string, periodId: string, cause: unknown = null) => {
    if (!this.isCurrent() || this.state.busy) return;
    this.set({ busy: true, error: null, uncertain: true, notice: 'Checking the backend ledger for this asset and period.' });
    try {
      const entries = await this.repository.getEntries({ asset: assetId, period: periodId });
      if (!this.isCurrent()) return;
      const found = entries.find(entry => entry.assetId === assetId && entry.periodId === periodId);
      if (found) {
        this.set({ entry: found, uncertain: false, notice: 'The backend confirms this period is posted. Asset balances are being refreshed.' });
      } else {
        this.set({ entry: null, uncertain: false, error: cause, notice: 'No posted entry exists in the latest backend read. Review the period and retry when ready.' });
      }
      await this.invalidate(assetId);
    } catch {
      this.set({ uncertain: true, error: cause, notice: 'The ledger could not be checked. Posting remains unconfirmed and another attempt is disabled.' });
    } finally { this.set({ busy: false }); }
  };
}
