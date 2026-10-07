const observations = [
  { tag: 'DEMO-PLANT-014', asset: 'Standby generator', outcome: 'Matched', detail: 'Tag, location and custodian match the register.', tone: 'text-emerald-800 bg-emerald-50' },
  { tag: 'DEMO-VEH-008', asset: 'Utility vehicle', outcome: 'Location mismatch', detail: 'Observed at the North Yard; register location is Central Depot.', tone: 'text-amber-900 bg-amber-50' },
  { tag: 'DEMO-ITEM-003', asset: 'Unregistered workshop tool', outcome: 'Unregistered', detail: 'No matching asset tag found during the sample count.', tone: 'text-rose-800 bg-rose-50' },
];

export function MockVerificationView() {
  return <main className="space-y-5 p-4 md:p-6">
    <header className="rounded-xl border bg-white p-5">
      <p className="text-sm text-slate-500">Mock demo · Local data</p>
      <h1 className="mt-1 text-2xl font-bold">Physical verification</h1>
      <p className="mt-2 max-w-3xl text-sm text-slate-600">Sample campaign records show how physical observations can be compared with the asset register and exceptions reviewed. This screen is illustrative local data; it does not connect to Django or store evidence files.</p>
    </header>
    <section className="rounded-xl border bg-white p-5" aria-labelledby="campaign-heading">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="campaign-heading" className="text-lg font-semibold">Quarterly equipment count</h2><p className="mt-1 text-sm text-slate-600">Demo campaign · Central Depot and North Yard · 8–19 September 2025</p></div><span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-900">In review</span></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><Metric label="Observed" value="3 of 8"/><Metric label="Exceptions" value="2"/><Metric label="Coverage" value="38%"/></div>
    </section>
    <section className="rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">Sample observations</h2><div className="mt-3 space-y-3">{observations.map(row=><article key={row.tag} className="rounded-lg border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">{row.tag} · {row.asset}</h3><p className="mt-1 text-sm text-slate-600">{row.detail}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${row.tone}`}>{row.outcome}</span></div>{row.outcome !== 'Matched'&&<p className="mt-2 text-sm"><b>Exception:</b> {row.outcome === 'Unregistered' ? 'Review whether this item should be registered.' : 'Confirm physical placement and update the record if approved.'}</p>}<p className="mt-2 text-xs text-slate-500">Evidence metadata example: site count sheet · PDF · recorded by Demo Reviewer 02. No binary file is present in this mock screen.</p></article>)}</div></section>
  </main>;
}

function Metric({label,value}:{label:string;value:string}) { return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-xl font-bold text-slate-900">{value}</p></div>; }
