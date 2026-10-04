import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from './apiClient';
import { ApiError } from './apiError';
import { mapAccountingPeriodDto, mapDepreciationEntryDto, mapDepreciationScheduleDto, parseAccountingPeriodDto, parseDepreciationEntryDto, parseDepreciationScheduleDto } from './depreciationDtos';
import { DjangoDepreciationRepository } from './depreciationRepository';
import { DepreciationWorkflow } from './depreciationWorkflow';
import { json } from '../test/fixtures';

const id = '11111111-1111-4111-8111-111111111111';
const periodDto = { id, year:2026, month:1, status:'OPEN', opened_at:'2026-01-01T00:00:00Z', closed_at:null, closed_by:null, created_at:'2026-01-01T00:00:00Z', updated_at:'2026-01-01T00:00:00Z' };
const scheduleDto = { id, organization:id, asset_id:id, asset_tag:'F3-001', method:'SLM', capitalized_cost:'999999999999999999.99', depreciable_base:'999999999999999999.98', residual_value:'0.01', useful_life_months:36, start_date:'2026-01-02', end_date:'2028-12-31', periodic_depreciation:'27777777777777777.78', status:'ACTIVE', created_at:'2026-01-01T00:00:00Z', updated_at:'2026-01-01T00:00:00Z' };
const entryDto = { id, asset:id, asset_tag:'F3-001', schedule:id, accounting_period:id, year:2026, month:1, opening_book_value:'1001.00', depreciation_amount:'25.03', accumulated_depreciation:'25.03', closing_book_value:'975.97', posted_at:'2026-01-31T00:00:00Z', created_at:'2026-01-31T00:00:00Z', created_by:null };
const entry = mapDepreciationEntryDto(parseDepreciationEntryDto(entryDto));
function apiWith(fetcher: ReturnType<typeof vi.fn<typeof fetch>>) {
  const api = new ApiClient('/api/v1', fetcher);
  api.session = { accessToken:'smoke-token', generation:1, refresh:async () => {}, invalidate:() => {} };
  return api;
}

describe('F3 depreciation API contract', () => {
  it('maps periods and explicitly rejects unknown period statuses', () => {
    expect(mapAccountingPeriodDto(parseAccountingPeriodDto(periodDto))).toMatchObject({ id, year:2026, month:1, status:'OPEN', closedAt:null, closedBy:null });
    expect(mapAccountingPeriodDto(parseAccountingPeriodDto({ ...periodDto, status:'CLOSED', closed_at:'2026-02-01T00:00:00Z', closed_by:7 })).closedBy).toBe(7);
    expect(() => parseAccountingPeriodDto({ ...periodDto, status:'REOPENED' })).toThrow('depreciation API response');
    expect(() => parseAccountingPeriodDto({ ...periodDto, month:13 })).toThrow();
  });
  it('maps schedule and entry contracts without converting accounting decimals', () => {
    expect(mapDepreciationScheduleDto(parseDepreciationScheduleDto(scheduleDto))).toMatchObject({ capitalizedCost:'999999999999999999.99', depreciableBase:'999999999999999999.98', periodicDepreciation:'27777777777777777.78' });
    expect(mapDepreciationEntryDto(parseDepreciationEntryDto(entryDto))).toMatchObject({ openingBookValue:'1001.00', depreciationAmount:'25.03', accumulatedDepreciation:'25.03', closingBookValue:'975.97', createdBy:null });
    expect(parseDepreciationEntryDto({ ...entryDto, created_by:7 }).created_by).toBe(7);
    expect(() => parseDepreciationScheduleDto({ ...scheduleDto, method:'RBM' })).toThrow();
    expect(() => parseDepreciationEntryDto({ ...entryDto, depreciation_amount:25.03 })).toThrow();
    expect(() => parseDepreciationEntryDto(null)).toThrow();
  });
  it('uses actual period, schedule, entry and posting endpoints; POST never sends a depreciation amount', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(json({ count:1,next:null,previous:null,results:[periodDto] }))
      .mockResolvedValueOnce(json({ ...scheduleDto, asset_id:id })).mockResolvedValueOnce(json(entryDto));
    const repository = new DjangoDepreciationRepository(apiWith(fetcher));
    await expect(repository.getPeriods()).resolves.toMatchObject([{ status:'OPEN' }]);
    await repository.createSchedule(id);
    await repository.post(id,id);
    expect(fetcher.mock.calls[1][0]).toBe('/api/v1/depreciation/schedules/');
    expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toEqual({ asset_id:id });
    expect(fetcher.mock.calls[2][0]).toBe('/api/v1/depreciation/entries/post/');
    expect(JSON.parse(String(fetcher.mock.calls[2][1]?.body))).toEqual({ asset_id:id, period_id:id });
    expect(String(fetcher.mock.calls[2][1]?.body)).not.toContain('depreciation_amount');
  });
});

describe('F3 posting reconciliation and safety', () => {
  it('posts once, locks rapid repeated calls, and refreshes scoped backend state', async () => {
    let resolvePost!: (value: typeof entry) => void;
    const post = vi.fn(() => new Promise<typeof entry>(resolve => { resolvePost = resolve; }));
    const repo = { post, getEntries:vi.fn(), };
    const invalidate = vi.fn(async () => {});
    const workflow = new DepreciationWorkflow(repo, () => true, invalidate);
    const first = workflow.post(id,id); const second = workflow.post(id,id);
    expect(post).toHaveBeenCalledTimes(1); expect(workflow.getSnapshot().busy).toBe(true);
    resolvePost(entry); await Promise.all([first, second]);
    expect(workflow.getSnapshot()).toMatchObject({ entry, uncertain:false, busy:false }); expect(invalidate).toHaveBeenCalledWith(id);
  });
  it('serializes same asset and period across remounted workflow instances', async () => {
    let resolvePost!: (value: typeof entry) => void;
    const repo = { post:vi.fn(() => new Promise<typeof entry>(resolve => { resolvePost = resolve; })), getEntries:vi.fn().mockResolvedValue([entry]) };
    const first = new DepreciationWorkflow(repo, () => true, async () => {});
    const second = new DepreciationWorkflow(repo, () => true, async () => {});
    const firstAttempt = first.post(id,id); const secondAttempt = second.post(id,id);
    expect(repo.post).toHaveBeenCalledTimes(1); expect(second.getSnapshot().uncertain).toBe(true);
    resolvePost(entry); await Promise.all([firstAttempt,secondAttempt]);
    expect(repo.post).toHaveBeenCalledTimes(1); expect(second.getSnapshot().entry).toEqual(entry);
  });
  it('reconciles an ambiguous response to an existing posted ledger entry without reposting', async () => {
    const repo = { post:vi.fn().mockRejectedValue(new ApiError('network','offline')), getEntries:vi.fn().mockResolvedValue([entry]) };
    const invalidate = vi.fn(async () => {}); const workflow = new DepreciationWorkflow(repo, () => true, invalidate);
    await workflow.post(id,id);
    expect(repo.post).toHaveBeenCalledTimes(1); expect(repo.getEntries).toHaveBeenCalledWith({ asset:id, period:id });
    expect(workflow.getSnapshot()).toMatchObject({ entry, uncertain:false, busy:false }); expect(invalidate).toHaveBeenCalledTimes(1);
  });
  it('allows a new attempt only after a successful ledger read proves no entry exists', async () => {
    const cause = new ApiError('network','offline');
    const repo = { post:vi.fn().mockRejectedValueOnce(cause), getEntries:vi.fn().mockResolvedValue([]) };
    const invalidate = vi.fn(async () => {}); const workflow = new DepreciationWorkflow(repo, () => true, invalidate);
    await workflow.post(id,id);
    expect(workflow.getSnapshot()).toMatchObject({ uncertain:false, entry:null, error:cause });
    expect(repo.post).toHaveBeenCalledTimes(1);
    expect(invalidate).toHaveBeenCalledWith(id);
  });
  it('keeps uncertain state and blocks another POST when reconciliation itself fails', async () => {
    const repo = { post:vi.fn().mockRejectedValue(new ApiError('server','failed')), getEntries:vi.fn().mockRejectedValue(new ApiError('network','offline')) };
    const workflow = new DepreciationWorkflow(repo, () => true, async () => {});
    await workflow.post(id,id); await workflow.post(id,id);
    expect(workflow.getSnapshot()).toMatchObject({ uncertain:true, entry:null }); expect(repo.post).toHaveBeenCalledTimes(1);
  });
  it('does not publish a response after the authenticated generation ends', async () => {
    let current = true; const repo = { post:vi.fn().mockResolvedValue(entry), getEntries:vi.fn() };
    const workflow = new DepreciationWorkflow(repo, () => current, async () => {});
    current = false; await workflow.post(id,id);
    expect(repo.post).not.toHaveBeenCalled(); expect(workflow.getSnapshot().entry).toBeNull();
  });
  it('does not publish or invalidate a result if the user changes during posting', async () => {
    let current = true; let resolvePost!: (value: typeof entry) => void;
    const repo = { post:vi.fn(() => new Promise<typeof entry>(resolve => { resolvePost = resolve; })), getEntries:vi.fn() };
    const invalidate = vi.fn(async () => {}); const workflow = new DepreciationWorkflow(repo, () => current, invalidate);
    const pending = workflow.post(id,id); current = false; resolvePost(entry); await pending;
    expect(workflow.getSnapshot().entry).toBeNull(); expect(invalidate).not.toHaveBeenCalled();
  });
});
