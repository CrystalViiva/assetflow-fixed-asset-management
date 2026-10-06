import { ErrorState, LoadingState } from '../components/common/AsyncState';
import { useAuth } from '../auth/AuthProvider';
import { useDashboardMetrics } from '../services/dashboardQueries';
import { DashboardGroup, DashboardMetrics } from '../services/dashboardDtos';

const readableRoles = ['ADMIN', 'ASSET_MANAGER', 'ACCOUNTANT', 'DEPARTMENT_MANAGER'];

export function formatExactMoney(value: string, currency: string): string {
  const [whole, fraction = '00'] = value.split('.');
  const grouped = new Intl.NumberFormat('en-NG', { maximumFractionDigits: 0 }).format(BigInt(whole));
  const parts = new Intl.NumberFormat('en-NG', { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).formatToParts(0);
  const prefix = parts.slice(0, parts.findIndex(part => part.type === 'integer')).map(part => part.value).join('');
  const suffix = parts.slice(parts.findIndex(part => part.type === 'fraction') + 1).map(part => part.value).join('');
  return `${prefix}${grouped}.${fraction}${suffix}`;
}

export function BackendDashboardView({ onNavigate }: { onNavigate: (route: string) => void }) {
  const { role } = useAuth();
  const authorized = readableRoles.includes(role ?? '');
  const query = useDashboardMetrics(authorized);
  if (!authorized) return <section className="p-6"><h1 className="text-2xl font-bold">Operational dashboard</h1><p role="alert" className="mt-3 rounded border bg-white p-4">Your role cannot access organization financial analytics.</p></section>;
  if (query.isPending) return <LoadingState label="Loading live organization dashboard…" />;
  if (query.isError) return <section className="space-y-4 p-4 md:p-6"><h1 className="text-2xl font-bold">Operational dashboard</h1><ErrorState error={query.error} retry={() => void query.refetch()} /></section>;
  const data = query.data;
  return <Dashboard data={data} onNavigate={onNavigate} refresh={() => void query.refetch()} refreshing={query.isFetching} />;
}

function Dashboard({ data, onNavigate, refresh, refreshing }: { data: DashboardMetrics; onNavigate: (route: string) => void; refresh: () => void; refreshing: boolean }) {
  const cards = [
    ['Currently held assets', String(data.portfolio.currentlyHeldAssets), `${data.portfolio.capitalizedAssets} capitalized · ${data.portfolio.disposedAssets} disposed`, 'all-assets'],
    ['Capitalized cost', formatExactMoney(data.financial.capitalizedCost, data.currency), `${data.portfolio.capitalizedAssets} held capitalized assets`, 'reports'],
    ['Current book value', formatExactMoney(data.financial.bookValue, data.currency), 'Current held capitalized assets', 'depreciation'],
    ['Accumulated depreciation', formatExactMoney(data.financial.accumulatedDepreciation, data.currency), 'Recognized on held capitalized assets', 'depreciation'],
    ['Open maintenance work', String(data.operations.openWorkOrders), `${data.operations.criticalOpenWorkOrders} critical`, 'maintenance'],
    ['Open assurance findings', String(data.controls.openAssuranceFindings), `${data.controls.openVerificationExceptions} verification exceptions`, 'assurance'],
  ] as const;
  return <main className="space-y-5 p-4 md:p-6">
    <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-5"><div><p className="text-sm text-slate-500">Live Django · {data.scope === 'department' ? 'Department scope' : 'Organization scope'}</p><h1 className="mt-1 text-2xl font-bold">Operational dashboard</h1><p className="mt-1 text-sm text-slate-600">Current PostgreSQL state · as of {new Date(data.asOf).toLocaleString()}</p></div><button className="rounded border px-4 py-2 text-sm font-semibold" onClick={refresh} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button></header>
    <section aria-label="Portfolio and operations KPIs" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([label, value, detail, route]) => <button key={label} onClick={() => onNavigate(route)} className="rounded-xl border bg-white p-4 text-left hover:border-blue-500"><span className="text-sm text-slate-600">{label}</span><strong className="mt-2 block text-2xl tabular-nums">{value}</strong><span className="mt-1 block text-xs text-slate-500">{detail}</span></button>)}</section>
    <section className="grid gap-4 xl:grid-cols-2"><GroupPanel title="Registered assets by lifecycle status" rows={data.distributions.status} valueLabel="Assets" /><GroupPanel title="Capitalized portfolio by category" rows={data.distributions.category} valueLabel="Book value" currency={data.currency} /><GroupPanel title="Capitalized portfolio by department" rows={data.distributions.department} valueLabel="Book value" currency={data.currency} /><GroupPanel title="Capitalized portfolio by location" rows={data.distributions.location} valueLabel="Book value" currency={data.currency} /></section>
    <section className="grid gap-4 xl:grid-cols-2"><SeriesPanel title="Posted depreciation by accounting period" rows={data.trends.postedDepreciation} currency={data.currency} /><SeriesPanel title="Capitalizations by month" rows={data.trends.capitalizations} currency={data.currency} /></section>
    <section className="grid gap-4 xl:grid-cols-2"><article className="rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">Operational queues</h2><div className="mt-3 grid grid-cols-2 gap-3 text-sm"><Metric label="Requested transfers" value={data.operations.requestedTransfers} route="transfers" onNavigate={onNavigate}/><Metric label="Approved transfers" value={data.operations.approvedTransfers} route="transfers" onNavigate={onNavigate}/><Metric label="Disposals pending approval" value={data.operations.pendingDisposals} route="disposals" onNavigate={onNavigate}/><Metric label="Approved disposals" value={data.operations.approvedDisposals} route="disposals" onNavigate={onNavigate}/><Metric label="Maintenance cost this month" value={formatExactMoney(data.operations.currentMonthMaintenanceCost, data.currency)} route="maintenance" onNavigate={onNavigate}/><Metric label="Posted depreciation this month" value={formatExactMoney(data.financial.currentMonthPostedDepreciation, data.currency)} route="depreciation" onNavigate={onNavigate}/><Metric label="Capitalized cost this month" value={formatExactMoney(data.financial.currentMonthCapitalizedCost, data.currency)} route="acquisitions" onNavigate={onNavigate}/><Metric label="Open physical verification exceptions" value={data.controls.openVerificationExceptions} route="verification" onNavigate={onNavigate}/></div></article>
    <article className="rounded-xl border bg-white p-5"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Recent asset activity</h2><button className="text-sm font-semibold text-blue-800 underline" onClick={() => onNavigate('audit-log')}>Open audit log</button></div>{data.recentActivity.length ? <ol className="mt-3 space-y-3">{data.recentActivity.map(row => <li key={row.id} className="border-b pb-2 last:border-0"><p className="font-medium">{row.action.replaceAll('_', ' ')} · {row.entityType.replaceAll('_', ' ')}</p><p className="text-xs text-slate-600">{row.actor ?? 'System'} · {new Date(row.timestamp).toLocaleString()}</p></li>)}</ol> : <p className="mt-3 text-sm text-slate-600">No asset audit events are available in this scope yet.</p>}</article></section>
    {data.portfolio.registeredAssets === 0 && <p role="status" className="rounded border bg-white p-4 text-sm">This organization has no registered assets yet. Dashboard measures show authoritative zero values where applicable.</p>}
  </main>;
}

function GroupPanel({ title, rows, valueLabel, currency }: { title: string; rows: DashboardGroup[]; valueLabel: string; currency?: string }) {
  const maximum = valueLabel === 'Assets' ? BigInt(Math.max(1, ...rows.map(row => row.count))) : rows.reduce((largest, row) => { const value = BigInt((row.bookValue ?? '0.00').replace('.', '')); return value > largest ? value : largest; }, 1n);
  const bar = (row: DashboardGroup) => {
    const value = valueLabel === 'Assets' ? BigInt(row.count) : BigInt((row.bookValue ?? '0.00').replace('.', ''));
    const units = value * 10000n / maximum;
    return `${units / 100n}.${String(units % 100n).padStart(2, '0')}%`;
  };
  return <article className="min-w-0 rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">{title}</h2>{rows.length ? <div className="mt-3 space-y-3">{rows.map(row => <div key={row.key}><div className="flex justify-between gap-4 text-sm"><span className="truncate">{row.label}</span><span className="shrink-0 tabular-nums">{valueLabel === 'Assets' ? row.count : <>{formatExactMoney(row.bookValue ?? '0.00', currency ?? 'NGN')} <span className="text-xs text-slate-500">· {row.count} assets</span></>}</span></div><div className="mt-1 h-2 overflow-hidden rounded bg-slate-100"><div className="h-full bg-blue-700" style={{ width: bar(row) }} /></div></div>)}</div> : <p role="status" className="mt-3 text-sm text-slate-600">No data in this scope.</p>}</article>;
}

function SeriesPanel({ title, rows, currency }: { title: string; rows: { period: string; amount: string }[]; currency: string }) {
  return <article className="min-w-0 rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">{title}</h2><p className="text-xs text-slate-500">Only periods with posted/capitalized records are shown; this is not a reconstructed historical balance.</p>{rows.length ? <div className="mt-3 max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th className="pb-2">Period</th><th className="pb-2 text-right">Amount</th></tr></thead><tbody>{rows.slice(-12).map(row => <tr key={row.period} className="border-t"><td className="py-2">{row.period}</td><td className="py-2 text-right tabular-nums">{formatExactMoney(row.amount, currency)}</td></tr>)}</tbody></table></div> : <p role="status" className="mt-3 text-sm text-slate-600">No posted records are available.</p>}</article>;
}
function Metric({ label, value, route, onNavigate }: { label: string; value: string | number; route: string; onNavigate: (route: string) => void }) { return <button onClick={() => onNavigate(route)} className="rounded border p-3 text-left hover:border-blue-500"><span className="block text-xs text-slate-600">{label}</span><strong className="mt-1 block tabular-nums">{value}</strong></button>; }
