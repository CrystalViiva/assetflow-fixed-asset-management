import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { canManageAssets, canReadAcquisitions, useAcquisitions } from '../services/acquisitionQueries';
import { formatDecimal } from '../services/assetDtos';

export function BackendAcquisitions({ onSelectAsset, onNavigate }: { onSelectAsset: (id: string) => void; onNavigate: (route: string) => void }) {
  const { role } = useAuth();
  const [query, setQuery] = useState({ page: 1, search: '', status: '' });
  const result = useAcquisitions(query);
  if (!canReadAcquisitions(role)) return <p role="alert" className="p-6">Your role does not have acquisition access.</p>;
  return <section className="p-6 space-y-4"><div className="flex justify-between items-center"><h1 className="text-2xl font-bold">Capex & Acquisitions Ledger</h1>
    {canManageAssets(role) && <button className="bg-[#00288e] text-white p-3 rounded-lg" onClick={() => onNavigate('asset-create')}>Register new asset</button>}</div>
    <div className="flex gap-4 p-4 bg-white border rounded-xl"><label className="text-sm">Search acquisitions<input className="block mt-1 border rounded p-2" value={query.search} onChange={event => setQuery(current => ({ ...current, search:event.target.value, page:1 }))} /></label>
      <label className="text-sm">Acquisition status<select className="block mt-1 border rounded p-2" value={query.status} onChange={event => setQuery(current => ({ ...current, status:event.target.value, page:1 }))}><option value="">All</option><option value="DRAFT">Draft</option><option value="CAPITALIZED">Capitalized</option></select></label></div>
    {result.isPending ? <LoadingState label="Loading acquisitions…" /> : result.isError ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : <div className="bg-white border rounded-xl overflow-x-auto">
      {!result.data.data.length ? <p role="status" className="p-8">No acquisitions match these filters.</p> : <table className="w-full text-sm text-left"><caption className="sr-only">Real acquisition records</caption><thead className="bg-slate-50"><tr>{['Asset','Vendor / invoice','Acquired','Capitalization','Total cost','Status'].map(text => <th key={text} className="p-3" scope="col">{text}</th>)}</tr></thead>
        <tbody>{result.data.data.map(row => <tr key={row.id} className="border-t"><td className="p-3"><button className="text-blue-800 underline" onClick={() => onSelectAsset(row.assetId)}>{row.assetTag}</button><p>{row.assetName}</p></td><td className="p-3">{row.vendor || '—'}<p>{row.invoice || '—'}</p></td><td className="p-3">{row.acquisitionDate}</td><td className="p-3">{row.capitalizationDate || '—'}</td><td className="p-3 font-mono">{row.currency} {formatDecimal(row.totalCost)}</td><td className="p-3">{row.status}</td></tr>)}</tbody></table>}
      <div className="p-4 flex justify-between border-t"><span>{result.data.total} acquisitions · Page {query.page} of {result.data.totalPages}</span><div className="flex gap-3">
        <button disabled={!result.data.hasPrevious || result.isFetching} onClick={() => setQuery(current => ({ ...current,page:current.page-1 }))}>Previous</button><button disabled={!result.data.hasNext || result.isFetching} onClick={() => setQuery(current => ({ ...current,page:current.page+1 }))}>Next</button></div></div>
    </div>}
  </section>;
}

export function AssetAcquisitionPanel({ assetId, onNavigate }: { assetId: string; onNavigate: (route: string) => void }) {
  const { role } = useAuth();
  const result = useAcquisitions({ page:1,asset:assetId });
  if (!canReadAcquisitions(role)) return <p className="p-5 text-sm text-slate-500">Acquisition records are unavailable to your role.</p>;
  if (result.isPending) return <LoadingState label="Loading acquisition…" />;
  if (result.isError) return <ErrorState error={result.error} retry={() => void result.refetch()} />;
  const acquisition = result.data.data[0];
  return <section className="p-6 bg-white border rounded-xl space-y-4"><h2 className="font-semibold text-lg">Acquisition & Capitalization</h2>
    {!acquisition ? <p>No acquisition recorded for this asset.</p> : <>
      <p>{acquisition.status} · {acquisition.currency} <strong>{formatDecimal(acquisition.totalCost)}</strong> · Backend total</p>
      <dl className="grid md:grid-cols-2 gap-4 text-sm">{[
        ['Vendor',acquisition.vendor || '—'],['Invoice',acquisition.invoice || '—'],['Reference',acquisition.reference || '—'],['Acquired',acquisition.acquisitionDate],['Capitalization date',acquisition.capitalizationDate || '—'],
        ['Purchase price',formatDecimal(acquisition.costs.purchase)],['Freight / haulage',formatDecimal(acquisition.costs.freight)],['Installation',formatDecimal(acquisition.costs.installation)],['Civil works',formatDecimal(acquisition.costs.civil)],['Other directly attributable costs',formatDecimal(acquisition.costs.other)],
      ].map(([label,value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd>{value}</dd></div>)}</dl><p className="text-sm whitespace-pre-wrap">{acquisition.notes}</p>
    </>}
    {canManageAssets(role) && acquisition?.status !== 'CAPITALIZED' && <button className="text-blue-800 underline" onClick={() => onNavigate(`asset-create/${assetId}`)}>Resume acquisition workflow</button>}
  </section>;
}
