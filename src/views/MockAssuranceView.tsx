const findings = [
  { code: 'LOCATION_MISMATCH', asset: 'DEMO-VEH-008 · Utility vehicle', severity: 'Medium', note: 'Observation location differs from the register location.', status: 'Open' },
  { code: 'UNREGISTERED_ASSET', asset: 'DEMO-ITEM-003 · Workshop tool', severity: 'Low', note: 'Physical observation has no matching registered asset.', status: 'Under review' },
];

export function MockAssuranceView() {
  return <main className="space-y-5 p-4 md:p-6">
    <header className="rounded-xl border bg-white p-5"><p className="text-sm text-slate-500">Mock demo · Local data</p><h1 className="mt-1 text-2xl font-bold">Assurance &amp; reconciliation</h1><p className="mt-2 max-w-3xl text-sm text-slate-600">Illustrative findings based on sample register and verification records. The Django application runs deterministic evaluations against frozen inputs and publishes findings; this local demo displays example outcomes only and does not execute assurance runs.</p></header>
    <section className="rounded-xl border bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Sample physical verification review</h2><p className="mt-1 text-sm text-slate-600">Demo run · completed 19 September 2025 · 8 sample assets evaluated</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">Illustrative results</span></div><div className="mt-4 grid gap-3 sm:grid-cols-3"><Metric label="Evaluated" value="8 assets"/><Metric label="Findings" value="2"/><Metric label="Resolved" value="0"/></div></section>
    <section className="rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">Example findings</h2><div className="mt-3 space-y-3">{findings.map(item=><article key={item.code} className="rounded-lg border p-4"><div className="flex flex-wrap justify-between gap-2"><div><h3 className="font-semibold">{item.code}</h3><p className="mt-1 text-sm text-blue-800">{item.asset}</p><p className="mt-2 text-sm text-slate-600">{item.note}</p></div><div className="flex gap-2 text-xs"><span className="h-fit rounded bg-amber-50 px-2 py-1 font-semibold text-amber-900">{item.severity}</span><span className="h-fit rounded bg-slate-100 px-2 py-1 font-semibold">{item.status}</span></div></div><p className="mt-3 text-xs text-slate-500">Sample finding data · no external review or certification is represented.</p></article>)}</div></section>
  </main>;
}

function Metric({label,value}:{label:string;value:string}) { return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-xl font-bold text-slate-900">{value}</p></div>; }
