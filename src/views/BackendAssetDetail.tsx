import { useAsset } from '../services/assetQueries';
import { formatDecimal } from '../services/assetDtos';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { AssetAcquisitionPanel } from './BackendAcquisitions';

export function BackendAssetDetail({ assetId, onNavigate }: { assetId: string; onNavigate: (route: string) => void }) {
  const result = useAsset(assetId);
  const back = <button onClick={() => onNavigate('all-assets')} className="text-[#00288e] underline text-sm">Back to Asset Register</button>;
  if (result.isPending) return <LoadingState label="Loading asset details…" />;
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
    {back}<div className="rounded-xl border bg-white p-6"><p className="text-sm text-slate-500">Django API · Asset Detail</p>
      <h1 className="text-2xl font-bold mt-2">{asset.tag} — {asset.name}</h1><p className="mt-3 text-slate-600 whitespace-pre-wrap">{asset.description || 'No description provided.'}</p></div>
    <nav aria-label="Asset detail sections" className="flex flex-wrap gap-2 rounded-xl bg-white border p-3 text-sm">
      <span aria-current="page" className="px-3 py-2 rounded bg-[#00288e] text-white">Overview</span>
      {['Depreciation','Assignments','Transfers','Maintenance','Documents','Audit'].map(tab => <button key={tab} disabled title="Integration pending" className="px-3 py-2 text-slate-500 disabled:cursor-not-allowed">{tab} · Integration pending</button>)}
    </nav>
    {result.isFetching && <p role="status" className="text-sm text-blue-700">Refreshing asset…</p>}
    <div className="bg-white border rounded-xl p-6"><h2 className="font-semibold text-lg">Overview</h2>
      <p className="text-xs text-slate-500 mt-2">Values are supplied by Django. Currency is not included in this API contract. Missing fields are shown as —.</p>
      <dl className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">{fields.map(([label,value]) => <div key={label}><dt className="text-xs font-medium text-slate-500">{label}</dt><dd className="mt-1 text-sm break-words">{value === null || value === undefined || value === '' ? '—' : value}</dd></div>)}</dl>
    </div>
    <AssetAcquisitionPanel assetId={asset.id} onNavigate={onNavigate} />
  </section>;
}
