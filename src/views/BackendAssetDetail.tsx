import { useState } from 'react';
import { useAsset } from '../services/assetQueries';
import { formatDecimal } from '../services/assetDtos';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { AssetAcquisitionPanel } from './BackendAcquisitions';
import { useDepreciationEntries, useDepreciationSchedules } from '../services/depreciationQueries';

export function BackendAssetDetail({ assetId, onNavigate }: { assetId: string; onNavigate: (route: string) => void }) {
  const [activeTab, setActiveTab] = useState<'Overview' | 'Depreciation'>('Overview');
  const result = useAsset(assetId);
  const schedules = useDepreciationSchedules(activeTab === 'Depreciation');
  const entries = useDepreciationEntries(assetId, undefined, activeTab === 'Depreciation');
  const back = <button onClick={() => onNavigate('all-assets')} className="text-[#00288e] underline text-sm">Back to Asset Register</button>;
  if (result.isPending) return <LoadingState label="Loading asset details..." />;
  if (result.isError) return <section className="p-6">{back}<ErrorState error={result.error} retry={() => void result.refetch()} /></section>;
  const asset = result.data;
  const fields: [string, string | number | null | undefined][] = [
    ['Asset ID', asset.id], ['Organization', asset.organization.name], ['Category', asset.category.name],
    ['Category code', asset.category.code], ['Department', asset.department?.name], ['Location', asset.location?.name],
    ['Lifecycle status', asset.status.replaceAll('_', ' ')], ['Condition', asset.condition], ['Serial number', asset.serialNumber],
    ['Manufacturer', asset.manufacturer], ['Model', asset.model], ['Acquisition date', asset.acquisitionDate],
    ['Capitalization date', asset.capitalizationDate], ['Available for use', asset.availableForUseDate],
    ['Purchase cost', formatDecimal(asset.purchaseCost)], ['Residual value', formatDecimal(asset.residualValue)],
    ['Accumulated depreciation', formatDecimal(asset.accumulatedDepreciation)], ['Current book value', formatDecimal(asset.bookValue)],
    ['Useful life (months)', asset.usefulLifeMonths], ['Depreciation method', asset.depreciationMethod],
    ['Created', asset.createdAt], ['Updated', asset.updatedAt],
  ];
  return <section className="p-4 md:p-6 space-y-4" aria-busy={result.isFetching}>
    {back}<div className="rounded-xl border bg-white p-6"><p className="text-sm text-slate-500">Django API - Asset Detail</p>
      <h1 className="text-2xl font-bold mt-2">{asset.tag} - {asset.name}</h1><p className="mt-3 text-slate-600 whitespace-pre-wrap">{asset.description || 'No description provided.'}</p></div>
    <nav aria-label="Asset detail sections" className="flex flex-wrap gap-2 rounded-xl bg-white border p-3 text-sm">
      {(['Overview','Depreciation'] as const).map(tab => <button key={tab} aria-current={activeTab === tab ? 'page' : undefined} onClick={() => setActiveTab(tab)} className={`px-3 py-2 rounded ${activeTab === tab ? 'bg-[#00288e] text-white' : 'text-slate-700 hover:bg-slate-100'}`}>{tab}</button>)}
      {['Assignments','Transfers','Maintenance','Documents','Audit'].map(tab => <button key={tab} disabled title="Integration pending" className="px-3 py-2 text-slate-500 disabled:cursor-not-allowed">{tab} - Integration pending</button>)}
    </nav>
    {result.isFetching && <p role="status" className="text-sm text-blue-700">Refreshing asset...</p>}
    {activeTab === 'Overview' && <>
      <div className="bg-white border rounded-xl p-6"><h2 className="font-semibold text-lg">Overview</h2>
        <p className="text-xs text-slate-500 mt-2">Values are supplied by Django. Currency is not included in this API contract. Missing fields are shown as —.</p>
        <dl className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">{fields.map(([label,value]) => <div key={label}><dt className="text-xs font-medium text-slate-500">{label}</dt><dd className="mt-1 text-sm break-words">{value === null || value === undefined || value === '' ? '—' : value}</dd></div>)}</dl>
      </div>
      <AssetAcquisitionPanel assetId={asset.id} onNavigate={onNavigate} />
    </>}
    {activeTab === 'Depreciation' && <div className="space-y-4">
      <section className="bg-white border rounded-xl p-6"><h2 className="font-semibold text-lg">Depreciation policy - backend asset state</h2>
        <dl className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <Fact label="Method" value={asset.depreciationMethod} /><Fact label="Capitalized cost" value={formatDecimal(asset.purchaseCost)} />
          <Fact label="Residual value" value={formatDecimal(asset.residualValue)} /><Fact label="Useful life" value={asset.usefulLifeMonths === null ? 'Not provided' : `${asset.usefulLifeMonths} months`} />
          <Fact label="Available for use" value={asset.availableForUseDate ?? 'Not provided'} /><Fact label="Accumulated depreciation - posted" value={formatDecimal(asset.accumulatedDepreciation)} />
          <Fact label="Current book value - backend" value={formatDecimal(asset.bookValue)} />
        </dl>
      </section>
      {schedules.isPending && <LoadingState label="Loading backend depreciation schedule..." />}
      {schedules.isError && <ErrorState error={schedules.error} retry={() => void schedules.refetch()} />}
      {!schedules.isPending && !schedules.isError && (() => {
        const schedule = schedules.data.find(row => row.assetId === asset.id);
        return schedule ? <section className="bg-white border rounded-xl p-6"><h3 className="font-semibold">Backend schedule - {schedule.status}</h3><p className="mt-1 text-sm text-slate-600">Frozen assumptions; the API does not expose per-period projections.</p><dl className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <Fact label="Schedule period" value={`${schedule.startDate} to ${schedule.endDate}`} /><Fact label="Depreciable base" value={formatDecimal(schedule.depreciableBase)} /><Fact label="Residual floor" value={formatDecimal(schedule.residualValue)} /><Fact label="Nominal periodic amount" value={formatDecimal(schedule.periodicDepreciation)} />
        </dl></section> : <section className="bg-white border rounded-xl p-6"><h3 className="font-semibold">No depreciation schedule</h3><p className="mt-1 text-sm text-slate-600">No schedule is fabricated for this asset.</p></section>;
      })()}
      <section className="bg-white border rounded-xl p-6"><h3 className="font-semibold">Posted depreciation entries</h3><p className="mt-1 text-sm text-slate-600">Posted values are ledger records. Schedule assumptions above are not posted entries.</p>
        {entries.isPending && <LoadingState label="Loading posted depreciation entries..." />}{entries.isError && <ErrorState error={entries.error} retry={() => void entries.refetch()} />}
        {!entries.isPending && !entries.isError && (entries.data.length ? <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="p-2">Period</th><th className="p-2 text-right">Opening</th><th className="p-2 text-right">Posted amount</th><th className="p-2 text-right">Accumulated</th><th className="p-2 text-right">Closing</th></tr></thead><tbody>{entries.data.map(row => <tr key={row.id} className="border-b"><td className="p-2">{row.year}-{String(row.month).padStart(2,'0')} - POSTED</td><td className="p-2 text-right">{formatDecimal(row.openingBookValue)}</td><td className="p-2 text-right">{formatDecimal(row.depreciationAmount)}</td><td className="p-2 text-right">{formatDecimal(row.accumulatedDepreciation)}</td><td className="p-2 text-right">{formatDecimal(row.closingBookValue)}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-slate-600">No posted ledger entries.</p>)}
      </section>
    </div>}
  </section>;
}
function Fact({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words font-medium">{value}</dd></div>; }
