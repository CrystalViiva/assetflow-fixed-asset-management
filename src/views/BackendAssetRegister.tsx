import { useState } from 'react';
import { useAssets } from '../services/assetQueries';
import { AssetQuery, defaultAssetQuery } from '../services/djangoApiBridge';
import { assetStatuses, formatDecimal } from '../services/assetDtos';
import { EmptyState, ErrorState, LoadingState } from '../components/common/AsyncState';
import { ReferenceSelect } from '../components/common/ReferenceSelect';
import { useAuth } from '../auth/AuthProvider';
import { canManageAssets } from '../services/acquisitionQueries';

export function updateAssetFilters(query: AssetQuery, update: Partial<AssetQuery>): AssetQuery {
  return { ...query, ...update, page: 1 };
}
export function BackendAssetRegister({ onSelectAsset, globalSearch }: { onSelectAsset: (id: string) => void; globalSearch: string }) {
  const { role } = useAuth();
  const [query, setQuery] = useState<AssetQuery>({ ...defaultAssetQuery, search: globalSearch });
  const [lastGlobalSearch, setLastGlobalSearch] = useState(globalSearch);
  // Synchronize before rendering children: never request/render the old page with a new search.
  if (lastGlobalSearch !== globalSearch) {
    setLastGlobalSearch(globalSearch);
    setQuery(current => updateAssetFilters(current, { search: globalSearch }));
  }
  const result = useAssets(query);
  const change = (update: Partial<AssetQuery>) => setQuery(current => updateAssetFilters(current, update));
  const inputClass = 'block mt-1 w-full rounded-md border border-slate-300 p-2 bg-white text-sm';
  return <section className="p-4 md:p-6 space-y-4">
    <div className="flex items-center justify-between gap-4"><div><h1 className="text-2xl font-bold">Asset Register</h1>
      <p className="text-sm text-slate-500 mt-1">Django API · Asset records</p></div>
      {canManageAssets(role) && <a className="bg-[#00288e] text-white rounded-lg px-4 py-2 text-sm" href="#asset-create">Register new asset</a>}
      <button className="border rounded-lg px-4 py-2 text-sm bg-white disabled:opacity-50" disabled={result.isFetching} onClick={() => void result.refetch()}>Refresh</button></div>
    <div className="bg-white rounded-xl border p-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <label className="text-sm font-medium sm:col-span-2">Search assets<input className={inputClass} value={query.search} onChange={e => change({ search: e.target.value })} placeholder="Tag, name, serial, model, manufacturer, description" /></label>
      <label className="text-sm font-medium">Status<select className={inputClass} value={query.status} onChange={e => change({ status: e.target.value })}><option value="">All statuses</option>{assetStatuses.map(status => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select></label>
      <label className="text-sm font-medium">Order by<select className={inputClass} value={query.ordering} onChange={e => change({ ordering: e.target.value })}>
        <option value="tag">Asset tag (ascending)</option><option value="-tag">Asset tag (descending)</option>
        <option value="name">Name (ascending)</option><option value="-name">Name (descending)</option>
        <option value="-acquisitionDate">Acquisition date (newest)</option><option value="-purchaseCost">Purchase cost (highest)</option><option value="-bookValue">Book value (highest)</option>
      </select></label>
      {(['category', 'department', 'location'] as const).map(field => <ReferenceSelect key={field} kind={field === 'category' ? 'categories' : field === 'department' ? 'departments' : 'locations'} label={field[0].toUpperCase()+field.slice(1)} value={query[field]} onChange={value => change({ [field]:value })} />)}
      <label className="text-sm font-medium">Rows per page<select className={inputClass} value={query.pageSize} onChange={e => change({ pageSize: Number(e.target.value) })}>{[10,25,50,100].map(size => <option key={size}>{size}</option>)}</select></label>
      <p className="text-xs text-slate-500 sm:col-span-2 lg:col-span-4">Filters run on the server. Custody, warranty, cost-range and audit quick filters are not available in Django mode. Amounts use the organization's accounting currency; the asset API does not expose its code.</p>
    </div>
    <div className="bg-white rounded-xl border overflow-hidden" aria-busy={result.isFetching}>
      {result.isPending ? <LoadingState /> : result.isError ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : <>
        {result.isFetching && <div role="status" className="px-4 py-2 text-sm text-blue-700">Refreshing assets…</div>}
        {!result.data.data.length ? <EmptyState /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <caption className="sr-only">Asset register from Django</caption><thead className="bg-slate-50 text-slate-600"><tr>{['Asset','Category','Department','Location','Status','Purchase cost','Book value'].map(title => <th key={title} scope="col" className="p-3">{title}</th>)}</tr></thead>
          <tbody>{result.data.data.map(asset => <tr key={asset.id} className="border-t hover:bg-blue-50/40">
            <td className="p-3"><button onClick={() => onSelectAsset(asset.id)} className="font-semibold text-[#00288e] text-left underline underline-offset-2">{asset.tag}</button><div className="mt-1">{asset.name}</div></td>
            <td className="p-3">{asset.category.name}</td><td className="p-3">{asset.department?.name || '—'}</td><td className="p-3">{asset.location?.name || '—'}</td>
            <td className="p-3 text-xs">{asset.status.replaceAll('_',' ')}</td><td className="p-3 font-mono whitespace-nowrap">{formatDecimal(asset.purchaseCost)}</td><td className="p-3 font-mono whitespace-nowrap">{formatDecimal(asset.bookValue)}</td>
          </tr>)}</tbody></table></div>}
        <div className="p-4 border-t flex flex-wrap gap-4 justify-between items-center text-sm">
          <span>{result.data.total} assets · Page {result.data.page} of {result.data.totalPages}</span><div className="flex gap-2">
            <button className="border rounded px-3 py-2 disabled:opacity-40" disabled={!result.data.hasPrevious || result.isFetching} onClick={() => setQuery(current => ({ ...current, page: current.page - 1 }))}>Previous</button>
            <button className="border rounded px-3 py-2 disabled:opacity-40" disabled={!result.data.hasNext || result.isFetching} onClick={() => setQuery(current => ({ ...current, page: current.page + 1 }))}>Next</button>
          </div></div>
      </>}
    </div>
  </section>;
}
