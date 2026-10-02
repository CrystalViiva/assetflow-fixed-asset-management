import { ApiError } from './apiError';
import { AcquisitionRecord, AssetRecord } from './assetDtos';
import { AcquisitionForm, createAcquisitionDto, createAssetDto } from './acquisitionForm';
import { DjangoAssetRepository } from './djangoApiBridge';

type Phase = 'editing' | 'review-existing' | 'asset-created' | 'acquisition-recorded' | 'capitalized';
type Operation = 'asset' | 'acquisition' | 'capitalization';
export interface WorkflowState {
  phase: Phase; busy: boolean; asset: AssetRecord | null; acquisition: AcquisitionRecord | null;
  error: unknown; uncertain: Operation | null; reservedTag: string; notice: string;
}
type WorkflowRepository = Pick<DjangoAssetRepository, 'createAsset' | 'getAssetByTag' | 'getAssetById' | 'getAcquisitionForAsset' | 'createAcquisition' | 'updateAcquisition' | 'capitalizeAcquisition'>;

/** Transient multi-request workflow. No transaction or rollback across requests is implied. */
export class AcquisitionWorkflow {
  private state: WorkflowState = { phase: 'editing', busy: false, asset: null, acquisition: null, error: null, uncertain: null, reservedTag: '', notice: '' };
  private listeners = new Set<() => void>();
  constructor(private readonly repository: WorkflowRepository, private readonly isCurrent: () => boolean,
    private readonly invalidate: () => Promise<unknown>) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private check() { if (!this.isCurrent()) throw new ApiError('authentication', 'Your session has ended.'); }
  private set(update: Partial<WorkflowState>) { this.check(); this.state = { ...this.state, ...update }; this.listeners.forEach(listener => listener()); }
  private async run(operation: Operation | null, action: () => Promise<void>) {
    this.check();
    if (this.state.busy) return; // Synchronous lock covers Enter/click and same-tick calls.
    this.set({ busy: true, error: null, notice: '' });
    try { await action(); }
    catch (error) {
      if (!this.isCurrent()) return;
      const ambiguous = operation && (!(error instanceof ApiError) || ['network', 'server', 'contract'].includes(error.kind));
      const definitelyRejected = error instanceof ApiError && ['validation', 'authorization', 'conflict', 'not-found'].includes(error.kind);
      this.set({ error, uncertain: ambiguous ? operation : this.state.uncertain,
        reservedTag: operation === 'asset' && definitelyRejected && !this.state.asset ? '' : this.state.reservedTag });
    } finally { if (this.isCurrent()) this.set({ busy: false }); }
  }
  private async changed() { this.check(); await this.invalidate(); this.check(); }
  create = (form: AcquisitionForm) => this.run('asset', async () => {
    if (this.state.phase !== 'editing' || this.state.uncertain) return;
    const dto = createAssetDto(form);
    if (this.state.reservedTag && dto.asset_tag !== this.state.reservedTag) throw new ApiError('validation', 'Keep the original tag while recovering this attempt.');
    this.set({ reservedTag: dto.asset_tag });
    const asset = await this.repository.createAsset(dto);
    this.set({ asset, phase: 'asset-created', notice: 'Draft asset saved. Acquisition has not yet been recorded.' });
    await this.changed();
  });
  record = (form: AcquisitionForm) => this.run('acquisition', async () => {
    if (!this.state.asset || this.state.uncertain || !['asset-created', 'acquisition-recorded'].includes(this.state.phase)) return;
    const dto = createAcquisitionDto(form, this.state.asset.id);
    // Read before create: one acquisition per asset; never POST a duplicate on a resumed workflow.
    const existing = await this.repository.getAcquisitionForAsset(this.state.asset.id);
    this.check();
    if (existing && !this.state.acquisition) {
      this.set({ acquisition: existing, phase: existing.status === 'CAPITALIZED' ? 'capitalized' : 'acquisition-recorded', notice: 'An acquisition already exists. Review its saved values before continuing.' });
      await this.changed(); return;
    }
    if (existing?.status === 'CAPITALIZED') { await this.reload(); return; }
    const acquisition = existing ? await this.repository.updateAcquisition(existing.id, dto) : await this.repository.createAcquisition(dto);
    this.set({ acquisition, phase: 'acquisition-recorded', notice: 'Acquisition saved. Review the backend total, then capitalize.' });
    await this.changed();
  });
  capitalize = () => this.run('capitalization', async () => {
    if (!this.state.acquisition || this.state.phase !== 'acquisition-recorded' || this.state.uncertain) return;
    const acquisition = await this.repository.capitalizeAcquisition(this.state.acquisition.id);
    if (acquisition.assetId !== this.state.asset?.id) throw new ApiError('contract', 'Capitalization response belongs to a different asset.');
    this.set({ acquisition, phase: 'capitalized', notice: 'Capitalization completed. The backend accounting state is authoritative.' });
    await this.changed();
    // A read failure cannot turn a confirmed capitalization into a retryable POST.
    try { this.set({ asset: await this.repository.getAssetById(acquisition.assetId) }); }
    catch (error) { if (this.isCurrent()) this.set({ error, notice: 'Capitalization completed; refresh the saved asset to view its latest state.' }); }
  });
  private async reload() {
    if (!this.state.asset) return;
    const asset = await this.repository.getAssetById(this.state.asset.id);
    this.check();
    const acquisition = await this.repository.getAcquisitionForAsset(asset.id);
    this.set({ asset, acquisition, uncertain: null,
      phase: acquisition?.status === 'CAPITALIZED' ? 'capitalized' : acquisition ? 'acquisition-recorded' : 'asset-created',
      notice: 'Saved backend state loaded. Review before continuing.' });
    await this.changed();
  }
  reconcile = () => this.run(null, async () => {
    if (this.state.asset) { await this.reload(); return; }
    if (!this.state.reservedTag) return;
    const asset = await this.repository.getAssetByTag(this.state.reservedTag);
    if (asset) this.set({ asset, phase: 'review-existing', uncertain: null, notice: 'An asset with this tag exists. Review its identity before explicitly resuming it.' });
    else this.set({ uncertain: null, notice: 'No asset found yet. You may check again or retry using the same reserved tag; the backend enforces tag uniqueness.' });
  });
  findExisting = (tag: string) => this.run(null, async () => {
    if (this.state.phase !== 'editing' || this.state.asset) return;
    const asset = await this.repository.getAssetByTag(tag.trim());
    if (!asset) throw new ApiError('not-found', 'No asset with that tag was found.');
    this.set({ asset, reservedTag: asset.tag, phase: 'review-existing', uncertain: null, notice: 'Review this existing asset before resuming.' });
  });
  resumeById = (id: string) => this.run(null, async () => {
    if (this.state.phase !== 'editing') return;
    const asset = await this.repository.getAssetById(id);
    this.set({ asset, reservedTag: asset.tag, phase: 'review-existing', notice: 'Review this asset before resuming its acquisition.' });
  });
  acceptExisting = () => this.run(null, () => this.reload());
}
