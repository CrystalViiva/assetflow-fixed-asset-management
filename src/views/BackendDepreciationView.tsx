import { FormEvent, useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { AssetRecord, formatDecimal } from '../services/assetDtos';
import { defaultAssetQuery } from '../services/djangoApiBridge';
import { useAllAssets } from '../services/assetQueries';
import { useAccountingPeriods, useDepreciationEntries, useDepreciationSchedules, depreciationKeys } from '../services/depreciationQueries';
import { useDepreciationWorkflow } from '../services/depreciationMutations';
import { depreciationRepository } from '../services/runtime';
import { errorMessage } from '../services/apiError';

const canPost = (role: string | null) => ['ADMIN','ASSET_MANAGER','ACCOUNTANT'].includes(role ?? '');
function periodName(year: number, month: number) { return `${year}-${String(month).padStart(2, '0')}`; }
function periodIdFromInput(value: string) { const [year, month] = value.split('-').map(Number); return { year, month }; }

export function BackendDepreciationView({ onNavigate, onSelectAsset }: { onNavigate: (route: string) => void; onSelectAsset: (assetId: string) => void }) {
  const { role, user, generation } = useAuth();
  const client = useQueryClient();
  const assetsQuery = useAllAssets({ ...defaultAssetQuery, pageSize: 100, status: 'ACTIVE' });
  const periodsQuery = useAccountingPeriods();
  const schedulesQuery = useDepreciationSchedules();
  const assets = assetsQuery.data?.data.filter(asset => asset.status === 'ACTIVE') ?? [];
  const schedules = schedulesQuery.data ?? [];
  const periods = periodsQuery.data ?? [];
  const [assetId, setAssetId] = useState('');
  const [periodId, setPeriodId] = useState('');
  const [newPeriod, setNewPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const asset: AssetRecord | undefined = assets.find(item => item.id === assetId) ?? assets[0];
  const schedule = schedules.find(item => item.assetId === asset?.id);
  const period = periods.find(item => item.id === periodId) ?? periods[0];
  const entriesQuery = useDepreciationEntries(asset?.id, period?.id, !!asset && !!period);
  const historyQuery = useDepreciationEntries(asset?.id, undefined, !!asset);
  const entry = entriesQuery.data?.find(item => item.assetId === asset?.id && item.periodId === period?.id);
  const posting = useDepreciationWorkflow(asset?.id, period?.id);
  useEffect(() => { if (!assetId && assets[0]) setAssetId(assets[0].id); else if (assetId && !assets.some(item => item.id === assetId)) setAssetId(assets[0]?.id ?? ''); }, [assets, assetId]);
  useEffect(() => { if (!periodId && periods[0]) setPeriodId(periods[0].id); else if (periodId && !periods.some(item => item.id === periodId)) setPeriodId(periods[0]?.id ?? ''); }, [periods, periodId]);

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: depreciationKeys.scope(user?.id, generation) }),
    client.invalidateQueries({ queryKey: ['django', user?.id, generation, 'assets'] }),
  ]);
  const scheduleMutation = useMutation({ mutationFn: (id: string) => depreciationRepository.createSchedule(id), onSuccess: refresh, onError: refresh, retry: false });
  const periodMutation = useMutation({ mutationFn: ({ year, month }: { year: number; month: number }) => depreciationRepository.createPeriod(year, month), onSuccess: async result => { await refresh(); setPeriodId(result.id); }, retry: false });
  const closeMutation = useMutation({ mutationFn: (id: string) => depreciationRepository.closePeriod(id), onSuccess: refresh, onError: refresh, retry: false });
  const expectedOpen = schedule?.status === 'ACTIVE' && asset?.status === 'ACTIVE' && period?.status === 'OPEN' && !entriesQuery.isPending && !entriesQuery.isError && !entry && !posting.state.entry && !posting.state.busy && !posting.state.uncertain;
  const postable = !!expectedOpen && canPost(role);
  const submitPeriod = (event: FormEvent) => { event.preventDefault(); const { year, month } = periodIdFromInput(newPeriod); if (Number.isInteger(year) && year >= 1900 && Number.isInteger(month) && month >= 1 && month <= 12) periodMutation.mutate({ year, month }); };

  if (assetsQuery.isPending || periodsQuery.isPending || schedulesQuery.isPending) return <LoadingState label="Loading depreciation, schedules, and accounting periods…" />;
  if (assetsQuery.isError) return <section className="p-6"><ErrorState error={assetsQuery.error} retry={() => void assetsQuery.refetch()} /></section>;
  if (periodsQuery.isError) return <section className="p-6"><ErrorState error={periodsQuery.error} retry={() => void periodsQuery.refetch()} /></section>;
  if (schedulesQuery.isError) return <section className="p-6"><ErrorState error={schedulesQuery.error} retry={() => void schedulesQuery.refetch()} /></section>;

  return <section className="w-full p-4 md:p-6 space-y-5" aria-busy={assetsQuery.isFetching || periodsQuery.isFetching || schedulesQuery.isFetching}>
    <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"><div><p className="text-xs text-slate-500">Accounting / Depreciation</p><h1 className="text-2xl font-bold text-slate-900">Depreciation & Accounting Periods</h1><p className="text-sm text-slate-600 mt-1">Schedules and posted balances come from the accounting API. The browser does not calculate depreciation.</p></div><button onClick={() => onNavigate('all-assets')} className="px-3 py-2 rounded border bg-white text-sm">Asset Register</button></header>
    <div className="grid lg:grid-cols-[1fr_1fr_auto] gap-3 rounded-xl border bg-white p-4 items-end">
      <label className="text-sm font-medium">Capitalized asset<select className="mt-1 block w-full border rounded px-3 py-2" value={asset?.id ?? ''} onChange={event => setAssetId(event.target.value)}><option value="">Select asset</option>{assets.map(item => <option key={item.id} value={item.id}>{item.tag} · {item.name}</option>)}</select></label>
      <label className="text-sm font-medium">Accounting period<select className="mt-1 block w-full border rounded px-3 py-2" value={period?.id ?? ''} onChange={event => setPeriodId(event.target.value)}><option value="">Select period</option>{periods.map(item => <option key={item.id} value={item.id}>{periodName(item.year,item.month)} · {item.status}</option>)}</select></label>
      {canPost(role) && <form onSubmit={submitPeriod} className="flex gap-2"><label className="sr-only" htmlFor="new-accounting-period">New accounting period</label><input id="new-accounting-period" className="border rounded px-2 py-2" type="month" min="1900-01" max="9999-12" value={newPeriod} onChange={event => setNewPeriod(event.target.value)} required /><button disabled={periodMutation.isPending} className="px-3 py-2 rounded bg-slate-800 text-white text-sm disabled:opacity-50">Open period</button></form>}
    </div>
    {(assetsQuery.data?.total === 0 || assets.length === 0) && <div className="rounded-xl border bg-white p-6"><h2 className="font-semibold">No capitalized active assets</h2><p className="text-sm text-slate-600 mt-1">Depreciation schedules can be created for active assets after capitalization.</p></div>}
    {periodMutation.isError && <p role="alert" className="text-sm text-red-700">Period could not be opened: {errorMessage(periodMutation.error)}</p>}
    {!periods.length && <div className="rounded-xl border bg-white p-6"><h2 className="font-semibold">No accounting periods</h2><p className="text-sm text-slate-600 mt-1">Periods are opened explicitly and are never created by posting.</p></div>}
    {asset && <>
      <div className="grid md:grid-cols-4 gap-3">
        <Metric label="Capitalized cost" value={formatDecimal(asset.purchaseCost)} />
        <Metric label="Residual value" value={formatDecimal(asset.residualValue)} />
        <Metric label="Accumulated depreciation · posted" value={formatDecimal(asset.accumulatedDepreciation)} />
        <Metric label="Current book value · backend" value={formatDecimal(asset.bookValue)} />
      </div>
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-lg">Schedule policy · {asset.tag}</h2><p className="text-sm text-slate-600">Policy comes from the asset and its frozen backend schedule. Available for use: {asset.availableForUseDate ?? 'not provided'}.</p></div>{asset.usefulLifeMonths && <button onClick={() => onSelectAsset(asset.id)} className="text-sm text-blue-800 underline">Open asset detail</button>}</div>
        {schedule ? <dl className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm"><Fact label="Method" value={schedule.method} /><Fact label="Schedule status" value={schedule.status} /><Fact label="Schedule start" value={schedule.startDate} /><Fact label="Schedule end" value={schedule.endDate} /><Fact label="Useful life" value={`${schedule.usefulLifeMonths} months`} /><Fact label="Capitalized cost" value={formatDecimal(schedule.capitalizedCost)} /><Fact label="Depreciable base" value={formatDecimal(schedule.depreciableBase)} /><Fact label="Residual floor" value={formatDecimal(schedule.residualValue)} /><Fact label="Nominal periodic amount · backend schedule" value={formatDecimal(schedule.periodicDepreciation)} /></dl> : canPost(role) && asset.status === 'ACTIVE' ? <div><p className="text-sm text-slate-600">No schedule exists. Creating one freezes the backend policy; no amount is calculated in the browser.</p><button className="mt-3 rounded bg-[#00288e] px-3 py-2 text-sm text-white disabled:opacity-50" disabled={scheduleMutation.isPending || !asset.usefulLifeMonths || !asset.availableForUseDate || asset.depreciationMethod !== 'SLM'} onClick={() => scheduleMutation.mutate(asset.id)}>{scheduleMutation.isPending ? 'Creating…' : 'Create backend schedule'}</button>{scheduleMutation.isError && <p role="alert" className="mt-2 text-sm text-red-700">Schedule could not be created: {errorMessage(scheduleMutation.error)}</p>}</div> : <p className="text-sm text-slate-600">No backend schedule is available for this asset.</p>}
      </div>
      {period && <div className="rounded-xl border bg-white p-5 space-y-4"><div className="flex flex-wrap justify-between items-center gap-3"><div><h2 className="text-lg font-semibold">{periodName(period.year,period.month)} · {period.status}</h2><p className="text-sm text-slate-600">Periods are monthly and organization-scoped. Closed periods cannot accept postings and cannot be reopened.</p></div>{canPost(role) && period.status === 'OPEN' && <button disabled={closeMutation.isPending} onClick={() => closeMutation.mutate(period.id)} className="rounded border px-3 py-2 text-sm disabled:opacity-50">{closeMutation.isPending ? 'Closing…' : 'Close period'}</button>}</div>
        {closeMutation.isError && <p role="alert" className="text-sm text-red-700">Period could not be closed: {errorMessage(closeMutation.error)}</p>}
        {period.status === 'CLOSED' && <p role="status" className="rounded bg-amber-50 p-3 text-sm text-amber-900">This period is closed. Posting is unavailable.</p>}
        {entriesQuery.isPending && <LoadingState label="Loading posted entries…" />}
        {entriesQuery.isError && <ErrorState error={entriesQuery.error} retry={() => void entriesQuery.refetch()} />}
        {!entriesQuery.isPending && !entriesQuery.isError && <>
          {entry && <div className="rounded border border-emerald-200 bg-emerald-50 p-4"><p className="font-semibold text-emerald-900">POSTED · Ledger entry {entry.id}</p><dl className="mt-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm"><Fact label="Opening book value" value={formatDecimal(entry.openingBookValue)} /><Fact label="Depreciation posted" value={formatDecimal(entry.depreciationAmount)} /><Fact label="Accumulated depreciation" value={formatDecimal(entry.accumulatedDepreciation)} /><Fact label="Closing book value" value={formatDecimal(entry.closingBookValue)} /><Fact label="Posted at" value={entry.postedAt} /></dl></div>}
          {!entry && <p className="text-sm text-slate-600">No posted entry exists for this selected asset and period. The backend schedule is not a period-by-period projection; no projected row is shown.</p>}
          {posting.state.notice && <p role="status" className="rounded bg-blue-50 p-3 text-sm text-blue-900">{posting.state.notice}</p>}
          {posting.state.error && <p role="alert" className="text-sm text-red-700">{errorMessage(posting.state.error)}</p>}
          {posting.state.entry && !entry && <p role="status" className="text-sm text-emerald-800">Posting confirmed by ledger reconciliation. Refreshing selected period state…</p>}
          {posting.state.uncertain && <button disabled={posting.state.busy} onClick={() => posting.reconcile(asset.id,period.id)} className="rounded border px-3 py-2 text-sm disabled:opacity-50">{posting.state.busy ? 'Checking ledger…' : 'Recheck ledger before retry'}</button>}
          {schedule && !entry && !posting.state.entry && canPost(role) && <button disabled={!postable} onClick={() => posting.post(asset.id,period.id)} className="rounded bg-[#00288e] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{posting.state.busy ? 'Posting / reconciling…' : posting.state.uncertain ? 'Posting status uncertain' : 'Post depreciation for selected asset'}</button>}
          {!canPost(role) && <p className="text-sm text-slate-600">Your role can read depreciation data but cannot post or manage periods.</p>}
        </>}
      </div>}
      <div className="rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">Posted history · {asset.tag}</h2><p className="text-sm text-slate-600 mt-1">Only entries returned by the ledger API appear here.</p>{historyQuery.isPending ? <LoadingState label="Loading posted history…" /> : historyQuery.isError ? <ErrorState error={historyQuery.error} retry={() => void historyQuery.refetch()} /> : historyQuery.data?.length ? <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="p-2">Period</th><th className="p-2 text-right">Opening</th><th className="p-2 text-right">Posted</th><th className="p-2 text-right">Accumulated</th><th className="p-2 text-right">Closing</th></tr></thead><tbody>{historyQuery.data.map(row => <tr key={row.id} className="border-b"><td className="p-2">{periodName(row.year,row.month)} · POSTED</td><td className="p-2 text-right">{formatDecimal(row.openingBookValue)}</td><td className="p-2 text-right">{formatDecimal(row.depreciationAmount)}</td><td className="p-2 text-right">{formatDecimal(row.accumulatedDepreciation)}</td><td className="p-2 text-right">{formatDecimal(row.closingBookValue)}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-slate-600">No posted depreciation entries for this asset.</p>}</div>
    </>}
    {periodsQuery.isFetching && <p role="status" className="text-xs text-slate-500">Refreshing accounting periods…</p>}
  </section>;
}
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-mono text-lg font-semibold">{value}</p></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words font-medium">{value}</dd></div>; }
