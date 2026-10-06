import { FormEvent, useState } from 'react';
import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { useAuditEvents } from '../services/auditQueries';
import { AuditFilters } from '../services/auditRepository';
import { uuidPattern } from '../services/assetDtos';
import { useAuth } from '../auth/AuthProvider';

const initial: AuditFilters = { page: 1, pageSize: 25, action: '', entityType: '', entityId: '', actor: '', search: '', dateFrom: '', dateTo: '', ordering: '-timestamp' };
function safeJson(value: unknown) { return JSON.stringify(value, null, 2); }

export function BackendAuditLogView({ onSelectAsset }: { onSelectAsset?: (id: string) => void }) {
  const [draft, setDraft] = useState(initial);
  const [filters, setFilters] = useState(initial);
  const { role } = useAuth();
  const permitted = role === 'ADMIN' || role === 'ASSET_MANAGER';
  const query = useAuditEvents(filters, permitted);
  const change = (field: keyof AuditFilters, value: string) => setDraft(current => ({ ...current, [field]: value, page: 1 }));
  const apply = (event: FormEvent) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); };
  return <main className="space-y-5 p-4 md:p-6" aria-busy={query.isFetching}>
    <header><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Governance / Traceability</p>
      <h1 className="mt-1 text-2xl font-bold">Audit Log</h1>
      <p className="mt-1 text-sm text-slate-600">Organization-scoped, append-only event records from Django domain services. Events are immutable through application controls; this is not a cryptographic ledger.</p>
    </header>
    <form onSubmit={apply} className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="text-sm">Search <input className="mt-1 w-full rounded border p-2" value={draft.search} onChange={e => change('search', e.target.value)} /></label>
      <label className="text-sm">Action <input className="mt-1 w-full rounded border p-2" value={draft.action} onChange={e => change('action', e.target.value)} /></label>
      <label className="text-sm">Entity type <input className="mt-1 w-full rounded border p-2" value={draft.entityType} onChange={e => change('entityType', e.target.value)} /></label>
      <label className="text-sm">Object ID <input className="mt-1 w-full rounded border p-2" value={draft.entityId} onChange={e => change('entityId', e.target.value)} /></label>
      <label className="text-sm">Actor email <input className="mt-1 w-full rounded border p-2" value={draft.actor} onChange={e => change('actor', e.target.value)} /></label>
      <label className="text-sm">From <input type="date" className="mt-1 w-full rounded border p-2" value={draft.dateFrom} onChange={e => change('dateFrom', e.target.value)} /></label>
      <label className="text-sm">To <input type="date" className="mt-1 w-full rounded border p-2" value={draft.dateTo} onChange={e => change('dateTo', e.target.value)} /></label>
      <label className="text-sm">Order <select className="mt-1 w-full rounded border p-2" value={draft.ordering} onChange={e => change('ordering', e.target.value)}><option value="-timestamp">Newest first</option><option value="timestamp">Oldest first</option></select></label>
      <button className="rounded bg-[#00288e] px-4 py-2 text-sm font-semibold text-white sm:col-span-2 lg:col-span-4">Apply filters</button>
    </form>
    {!permitted ? <p role="status" className="rounded-xl border bg-white p-8 text-center text-slate-600">Audit event access is available to administrators and asset managers.</p> : query.isPending ? <LoadingState label="Loading audit events…" /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : query.data.results.length === 0 ?
      <p role="status" className="rounded-xl border bg-white p-8 text-center text-slate-600">No audit events match these filters.</p> :
      <section className="space-y-3" aria-label="Audit events">
        {query.data.results.map(event => <article key={event.id} className="rounded-xl border bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><time className="text-sm text-slate-500" dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time>
              <h2 className="mt-1 font-semibold">{event.action.replaceAll('_', ' ')}</h2>
              <p className="text-sm text-slate-600">{event.actorEmail ?? 'System or deleted actor'} · {event.entityType} · <span className="font-mono text-xs">{event.entityId}</span></p></div>
            {event.entityType === 'ASSET' && uuidPattern.test(event.entityId) && onSelectAsset && <button className="rounded border px-3 py-1.5 text-sm text-[#00288e]" onClick={() => onSelectAsset(event.entityId)}>Open asset</button>}
          </div>
          <details className="mt-3 border-t pt-3"><summary className="cursor-pointer text-sm font-semibold">Safe event metadata and changes</summary>
            <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3"><div><dt className="font-semibold text-slate-500">Raw action</dt><dd className="break-all font-mono">{event.action}</dd></div><div><dt className="font-semibold text-slate-500">Entity type</dt><dd className="break-all font-mono">{event.entityType}</dd></div><div><dt className="font-semibold text-slate-500">Object ID</dt><dd className="break-all font-mono">{event.entityId}</dd></div></dl>
            <div className="mt-3 grid gap-3 lg:grid-cols-2"><div><h3 className="text-xs font-semibold uppercase text-slate-500">Changes</h3><pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs">{safeJson(event.changes)}</pre></div>
              <div><h3 className="text-xs font-semibold uppercase text-slate-500">Metadata</h3><pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs">{safeJson(event.metadata)}</pre></div></div>
          </details>
        </article>)}
        <nav className="flex items-center justify-between rounded-xl border bg-white p-3" aria-label="Audit pages">
          <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={filters.page <= 1 || !query.data.previous} onClick={() => setFilters(current => ({ ...current, page: current.page - 1 }))}>Previous</button>
          <span className="text-sm">{query.data.count} events · Page {filters.page}</span>
          <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={!query.data.next} onClick={() => setFilters(current => ({ ...current, page: current.page + 1 }))}>Next</button>
        </nav>
      </section>}
  </main>;
}
