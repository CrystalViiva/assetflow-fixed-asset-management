import { useState } from 'react';
import { ArrowRight, Boxes, Building2, ChartNoAxesCombined, ClipboardCheck, FileCheck2, Landmark, LockKeyhole, Menu, X } from 'lucide-react';
import { AssetFlowLogo } from '../components/common/AssetFlowLogo';

const lifecycle = [
  ['01','Acquire','Capture componentized costs and supporting records.'],
  ['02','Capitalize','Move eligible assets into the accounting register through controlled workflows.'],
  ['03','Depreciate','Post straight-line depreciation through defined accounting periods.'],
  ['04','Assign & transfer','Record custody and controlled movement between locations.'],
  ['05','Maintain','Manage plans, work orders, costs and completion history.'],
  ['06','Verify & assure','Compare physical observations with records and review deterministic findings.'],
  ['07','Dispose','Route derecognition through approval and record disposal outcomes.'],
];

const capabilities = [
  { icon: Landmark, title: 'Accounting control', text: 'Componentized acquisition, capitalization, useful life and residual value, posted SLM depreciation, periods, carrying value and disposal gain or loss.' },
  { icon: Building2, title: 'Operational custody', text: 'Organization, department, location and custodian records connect to controlled assignment, transfer and maintenance workflows.' },
  { icon: ClipboardCheck, title: 'Physical verification', text: 'Capture registered and unregistered observations, compare them with master records, and track resulting exceptions.' },
  { icon: FileCheck2, title: 'Deterministic assurance', text: 'Run backend evaluations against frozen inputs, then review published findings and their occurrence history.' },
  { icon: LockKeyhole, title: 'Traceable controls', text: 'Tenant-scoped permissions, role-aware workflows, application audit events and private verification evidence.' },
  { icon: ChartNoAxesCombined, title: 'Useful reporting', text: 'Live operational aggregates, durable report snapshots and CSV or JSON exports from completed snapshots.' },
];

export function PublicLandingPage({ authenticated, mockMode = false }: { authenticated: boolean; mockMode?: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const appLink = authenticated || mockMode ? '#dashboard' : '#login';
  const signInText = authenticated ? 'Open dashboard' : mockMode ? 'Open demo workspace' : 'Sign in';
  return <div className="landing min-h-screen bg-white text-slate-900">
    <header className="landing-header sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3.5 lg:px-8">
        <a href="#/" className="flex items-center gap-2.5 rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-700" aria-label="AssetFlow home">
          <AssetFlowLogo className="h-9 w-9" /><span className="text-xl font-bold tracking-tight text-[#0d2856]">AssetFlow</span>
        </a>
        <nav aria-label="Main navigation" className="hidden items-center gap-7 md:flex">
          <a className="landing-nav-link" href="#capabilities">Capabilities</a><a className="landing-nav-link" href="#controls">Controls</a><a className="landing-nav-link" href="#architecture">Architecture</a>
          <a className="rounded-lg bg-[#123b83] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#0d2e69] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700" href={appLink}>{signInText}</a>
        </nav>
        <button type="button" className="rounded-md p-2 text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-700 md:hidden" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
        </button>
      </div>
      {menuOpen && <nav aria-label="Mobile navigation" className="grid gap-1 border-t border-slate-200 px-5 py-3 md:hidden">
        <a onClick={() => setMenuOpen(false)} className="landing-mobile-link" href="#capabilities">Capabilities</a><a onClick={() => setMenuOpen(false)} className="landing-mobile-link" href="#controls">Controls</a><a onClick={() => setMenuOpen(false)} className="landing-mobile-link" href="#architecture">Architecture</a><a onClick={() => setMenuOpen(false)} className="landing-mobile-link font-semibold text-blue-800" href={appLink}>{signInText}</a>
      </nav>}
    </header>

    <main>
      <section className="landing-hero overflow-hidden border-b border-slate-200 bg-[linear-gradient(120deg,#f7f9fd_0%,#fff_64%,#f2f6fc_100%)]">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 py-16 md:py-24 lg:grid-cols-[1.05fr_.95fr] lg:px-8">
          <div>
            <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-[.13em] text-blue-900"><span className="h-1.5 w-1.5 rounded-full bg-blue-700" />Fixed asset management system</p>
            <h1 className="max-w-2xl text-4xl font-semibold leading-[1.08] tracking-[-.04em] text-[#10294f] sm:text-5xl lg:text-[3.65rem]">Control the complete lifecycle of every asset.</h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-slate-600 sm:text-lg">Bring acquisition, capitalization, depreciation, custody, maintenance, disposal, physical verification and assurance into one controlled system.</p>
            <div className="mt-8 flex flex-wrap items-center gap-3"><a href={appLink} className="inline-flex items-center gap-2 rounded-lg bg-[#123b83] px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#0d2e69] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">{mockMode && !authenticated ? 'Open demo workspace' : authenticated ? 'Open dashboard' : 'Sign in to AssetFlow'}<ArrowRight size={17} aria-hidden="true" /></a><a href="#capabilities" className="rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Explore capabilities</a></div>
            <p className="mt-5 text-xs text-slate-500">IAS 16-aligned straight-line depreciation workflows. Not a claim of full IFRS compliance.</p>
          </div>
          <div className="relative min-w-0" aria-label="Illustrative AssetFlow interface preview">
            <div className="absolute -inset-4 rounded-[2rem] bg-blue-100/70 blur-2xl" aria-hidden="true" />
            <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_28px_70px_-32px_rgba(15,38,82,.34)]">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3"><div className="flex items-center gap-2"><AssetFlowLogo className="h-6 w-6"/><span className="text-sm font-semibold text-slate-800">AssetFlow</span></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-medium text-slate-600">PRODUCT PREVIEW</span></div>
              <div className="grid min-h-[285px] grid-cols-[116px_1fr] sm:grid-cols-[150px_1fr]">
                <div className="space-y-3 border-r border-slate-100 bg-slate-50/80 p-3"><div className="rounded-md bg-blue-100 px-2 py-2 text-[10px] font-semibold text-blue-900">Dashboard</div><div className="preview-nav">Asset register</div><div className="preview-nav">Acquisitions</div><div className="preview-nav">Depreciation</div><div className="preview-nav">Maintenance</div><div className="preview-nav">Verification</div><div className="preview-nav">Reports</div></div>
                <div className="min-w-0 p-3 sm:p-5"><div className="flex items-start justify-between gap-2"><div><div className="text-[10px] uppercase tracking-wider text-slate-400">Workspace overview</div><div className="mt-1 text-sm font-semibold text-slate-800 sm:text-base">Operational dashboard</div></div><div className="rounded-md border border-slate-200 px-2 py-1 text-[9px] text-slate-500">Organization scope</div></div>
                  <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3"><div className="preview-kpi"><span>Controlled assets</span><b>—</b><small>Live, scoped measure</small></div><div className="preview-kpi"><span>Capitalized cost</span><b>—</b><small>Server-calculated</small></div><div className="preview-kpi hidden sm:block"><span>Book value</span><b>—</b><small>Current accounting state</small></div></div>
                  <div className="mt-3 rounded-lg border border-slate-200 p-3"><div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-slate-700">Portfolio by category</span><span className="text-[9px] text-slate-400">Illustrative layout</span></div><div className="mt-3 flex h-[68px] items-end gap-2 border-b border-slate-200 px-2">{[['h-8','bg-blue-200'],['h-12','bg-blue-200'],['h-7','bg-blue-200'],['h-14','bg-blue-200'],['h-10','bg-blue-700'],['h-16','bg-blue-200']].map(([height,color],i)=><div key={i} className={`${height} ${color} flex-1 rounded-t-sm`} />)}</div><div className="mt-2 flex items-center justify-between text-[8px] text-slate-400"><span>Categories</span><span>No organization data shown</span></div></div>
                </div>
              </div>
            </div>
            <p className="relative mt-3 text-right text-xs text-slate-500">Illustrative interface only · no live organization data</p>
          </div>
        </div>
      </section>

      <section id="capabilities" className="scroll-mt-24 mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-20">
        <div className="max-w-2xl"><p className="section-kicker">One connected lifecycle</p><h2 className="section-title">From acquisition record to accountable disposition.</h2><p className="mt-4 leading-7 text-slate-600">Keep financial treatment and day-to-day custody connected to the same governed asset record.</p></div>
        <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{lifecycle.map(([number,title,text],i)=><article key={number} className="lifecycle-card"><div className="flex items-center justify-between"><span className="text-xs font-semibold tracking-widest text-blue-700">{number}</span>{i<lifecycle.length-1&&<ArrowRight className="hidden text-slate-300 sm:block" size={16} aria-hidden="true"/>}</div><h3 className="mt-5 font-semibold text-slate-900">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></article>)}</div>
        <div className="mt-16 grid gap-10 lg:grid-cols-[.85fr_1.15fr]" id="controls"><div><p className="section-kicker">Financial & operational controls</p><h2 className="section-title">A clearer record of value, custody and action.</h2><p className="mt-4 leading-7 text-slate-600">Designed to keep accounting workflows explicit and operational evidence traceable, while leaving each change within its proper controlled process.</p><div className="mt-6 rounded-xl border border-blue-100 bg-blue-50/70 p-5"><div className="flex items-center gap-3"><Boxes className="text-blue-800" size={21}/><h3 className="font-semibold text-slate-900">Accounting workflows</h3></div><p className="mt-3 text-sm leading-6 text-slate-700">Componentized directly attributable cost, capitalization, useful life and residual value, straight-line depreciation postings, accounting periods, carrying value and disposal gain or loss.</p><p className="mt-3 text-xs leading-5 text-slate-500">Depreciation currently uses the straight-line method. Impairment accounting and other depreciation methods are not represented as available workflows.</p></div></div>
          <div className="grid gap-3 sm:grid-cols-2">{capabilities.map(({icon:Icon,title,text})=><article key={title} className="capability-card"><span className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-blue-800"><Icon size={20} aria-hidden="true"/></span><h3 className="font-semibold text-slate-900">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></article>)}</div></div>
      </section>

      <section id="architecture" className="scroll-mt-24 border-y border-slate-200 bg-slate-50"><div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 lg:grid-cols-2 lg:px-8 lg:py-20"><div><p className="section-kicker">Reporting & analytics</p><h2 className="section-title">Operational clarity, with durable reporting when you need it.</h2><p className="mt-4 leading-7 text-slate-600">The dashboard uses live transactional aggregates. Reports can be captured as durable snapshots and exported as CSV or JSON from completed snapshots.</p><div className="mt-6 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-700"><span className="architecture-node">Django + PostgreSQL</span><ArrowRight size={15}/><span className="architecture-node">Operational dashboard</span><ArrowRight size={15}/><span className="architecture-node">Snapshots & exports</span></div><p className="mt-4 text-sm leading-6 text-slate-500">Separate batch analytics use an Airflow extraction pipeline and PySpark curated data marts. The browser dashboard does not read Parquet marts.</p></div><div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="section-kicker">Engineering architecture</p><div className="mt-5 space-y-3"><div className="architecture-row"><span className="architecture-dot bg-blue-700"/><div><b>Application</b><p>React · TypeScript · TanStack Query</p></div></div><div className="architecture-row"><span className="architecture-dot bg-indigo-500"/><div><b>Domain API</b><p>Python · Django REST Framework</p></div></div><div className="architecture-row"><span className="architecture-dot bg-emerald-600"/><div><b>Persistence & tasks</b><p>PostgreSQL · Celery · Redis</p></div></div><div className="architecture-row"><span className="architecture-dot bg-amber-500"/><div><b>Batch analytics</b><p>Airflow extraction · versioned JSONL · PySpark · Parquet marts</p></div></div></div></div></div></section>

      <section className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-20"><div className="grid gap-10 lg:grid-cols-[.85fr_1.15fr]"><div><p className="section-kicker">Governed access</p><h2 className="section-title">Controls belong in the workflow and the server.</h2><p className="mt-4 leading-7 text-slate-600">AssetFlow combines authenticated access with organization-scoped authorization and role- and department-aware permissions enforced by Django.</p></div><div className="grid gap-3 sm:grid-cols-2">{['Backend-authoritative role checks','Organization and department scope','Application audit events','Controlled lifecycle transitions','Private verification evidence','Authenticated evidence access with size and SHA256 integrity metadata'].map(item=><div key={item} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-700"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-600" aria-hidden="true"/>{item}</div>)}</div></div></section>

      <section className="bg-[#10294f] text-white"><div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-5 py-12 sm:flex-row sm:items-center lg:px-8"><div><p className="text-sm font-medium text-blue-200">Bring your asset records into a more controlled lifecycle.</p><h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Ready to work in AssetFlow?</h2></div><a href={appLink} className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-[#10294f] hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">{authenticated ? 'Open dashboard' : 'Sign in to AssetFlow'}<ArrowRight size={17} aria-hidden="true"/></a></div></section>
    </main>
    <footer className="border-t border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-7 sm:flex-row sm:items-center sm:justify-between lg:px-8"><a href="#/" className="flex items-center gap-2 text-sm font-semibold text-slate-800"><AssetFlowLogo className="h-7 w-7"/>AssetFlow <span className="font-normal text-slate-500">· Fixed Asset Management System</span></a><div className="flex flex-wrap gap-5 text-sm text-slate-600"><a className="hover:text-blue-800" href="#capabilities">Capabilities</a><a className="hover:text-blue-800" href="#architecture">Architecture</a><a className="hover:text-blue-800" href={appLink}>{signInText}</a></div><span className="text-xs text-slate-400">© AssetFlow</span></div></footer>
  </div>;
}
