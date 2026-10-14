import { useEffect } from 'react';
import { ArrowDown, ArrowRight, Boxes, Building2, ChartNoAxesCombined, ClipboardCheck, Factory, GraduationCap, Landmark, PackageCheck, Wrench, Check } from 'lucide-react';
import { PublicHeader, PublicFooter } from '../components/marketing/PublicChrome';
import { AssetFlowLogo } from '../components/common/AssetFlowLogo';

const lifecycle = [
  ['01', 'Acquire', 'Capture costs, components and supporting records.'],
  ['02', 'Capitalize', 'Move eligible assets into the register through controlled workflows.'],
  ['03', 'Depreciate', 'Post straight-line depreciation within defined accounting periods.'],
  ['04', 'Assign & transfer', 'Record who is responsible and where equipment is used.'],
  ['05', 'Maintain', 'Manage plans, work orders, costs and completion history.'],
  ['06', 'Verify & assure', 'Compare physical observations with records and review findings.'],
  ['07', 'Dispose', 'Route derecognition through approval and record the outcome.'],
];

function ProductPreview() {
  return <div className="product-window" role="img" aria-label="Illustrative AssetFlow workspace with fictional asset records and sample values">
    <div className="product-window-top"><div className="flex items-center gap-2"><AssetFlowLogo className="h-6 w-6"/><strong>AssetFlow</strong></div><span className="preview-label">SYNTHETIC DATA  -  PREVIEW</span><span className="preview-avatar">AF</span></div>
    <div className="product-window-body"><aside className="product-sidebar"><p>WORKSPACE</p><b className="selected">Overview</b><b>Asset register</b><b>Acquisitions</b><b>Depreciation</b><b>Maintenance</b><b>Verification</b><b>Reports</b></aside>
      <div className="product-content"><div className="flex flex-wrap items-start justify-between gap-2"><div><span className="product-eyebrow">ASSET OVERVIEW</span><h3>Workspace overview</h3></div><span className="product-scope">Sample workspace</span></div>
        <div className="product-metrics"><div><span>Registered assets</span><b>1,284</b><small>6 categories</small></div><div><span>Capitalized cost</span><b>₦842.6m</b><small>Sample value</small></div><div><span>Carrying value</span><b>₦617.3m</b><small>Sample value</small></div></div>
        <div className="product-lower"><div className="product-chart"><div className="flex justify-between"><b>Asset value by category</b><span>Sample</span></div><div className="chart-plot"><div className="chart-grid"/><div className="chart-bar h-[48%]"/><div className="chart-bar h-[72%]"/><div className="chart-bar h-[56%]"/><div className="chart-bar h-[88%]"/></div><div className="chart-legend"><span>Plant</span><span>Vehicles</span><span>IT</span><span>Facilities</span></div></div>
          <div className="product-activity"><b>Recently updated</b>{[['AF-0194','Forklift  -  Plant','Assigned'],['AF-0218','Generator  -  Site B','Maintained'],['AF-0271','Workstation  -  HQ','Verified']].map(([id,label,status])=><div className="activity-row" key={id}><span className="activity-dot"/><div><strong>{label}</strong><small>{id}  -  Fictional sample</small></div><em>{status}</em></div>)}</div></div>
      </div>
    </div>
  </div>;
}

export function PublicLandingPage({ authenticated, mockMode = false, workspaceRoute = '#dashboard' }: { authenticated: boolean; mockMode?: boolean; workspaceRoute?: string }) {
  useEffect(() => {
    let frame = 0;
    const scroll = () => {
      const section = window.location.hash.replace(/^#\/?/, '').split('?')[0];
      cancelAnimationFrame(frame);
      if (section.startsWith('section-')) frame = requestAnimationFrame(() => document.getElementById(section)?.scrollIntoView({ block: 'start' }));
    };
    scroll();
    window.addEventListener('hashchange', scroll);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('hashchange', scroll); };
  }, []);
  return <div className="landing min-h-screen bg-white text-slate-900">
    <PublicHeader sections authenticated={authenticated} workspaceRoute={workspaceRoute} />
    <main id="public-main" tabIndex={-1}>
      <section className="landing-hero"><div className="hero-glow" aria-hidden="true"/><div className="hero-inner"><div className="hero-copy"><p className="hero-eyebrow"><span/> FIXED ASSET MANAGEMENT</p><h1>Know your assets.<br/><span>Control their value.</span></h1><p className="hero-description">Follow every fixed asset from acquisition and capitalization to custody, maintenance, verification and disposal — in one workspace.</p><div className="hero-actions"><a className="button-primary" href={mockMode && !authenticated ? '#request-demo' : '#get-started'}>{mockMode && !authenticated ? 'Request a demo' : 'Get started'}<ArrowRight size={17}/></a><a className="button-secondary" href="#section-product-preview">Explore the product<ArrowDown size={15}/></a></div><div className="hero-proof"><span className="proof-check"><Check size={14} aria-hidden="true" /></span> Built for accountable finance and operations teams</div></div><div id="section-product-preview" className="hero-product"><ProductPreview/><p className="product-preview-caption">Illustrative workspace · Fictional records and values</p><div className="preview-float"><span className="float-icon"><PackageCheck size={17}/></span><span><b>One controlled register</b><small>Financial and operational records</small></span></div></div></div><div className="hero-bottom"><span>ACQUISITION</span><i/><span>ACCOUNTING</span><i/><span>OPERATIONS</span><i/><span>ASSURANCE</span></div></section>

      <section className="trust-strip"><p>BUILT TO CONNECT FINANCIAL RECORDS WITH THE WORK THAT KEEPS ASSETS USEFUL</p><div><span><Landmark/>Finance</span><span><Building2/>Operations</span><span><ChartNoAxesCombined/>Asset accounting</span><span><ClipboardCheck/>Assurance</span></div></section>

      <section id="section-features" className="section-wrap lifecycle-section"><div className="section-heading"><p className="section-kicker">ONE CONNECTED LIFECYCLE</p><h2>From the first record<br/>to a clear disposition.</h2><p>Keep financial treatment and day-to-day custody connected to the same governed asset record.</p></div><div className="lifecycle-grid">{lifecycle.map(([number,title,text],i)=><article key={number} className="lifecycle-item"><div className="lifecycle-number">{number}{i < lifecycle.length - 1 && <ArrowRight size={15}/>}</div><h3>{title}</h3><p>{text}</p></article>)}</div></section>

      <section className="feature-showcase"><div className="feature-row"><div className="feature-copy"><p className="section-kicker">FINANCE, WITH CONTEXT</p><h2>Understand the value behind every record.</h2><p>Capture directly attributable costs, capitalize through an explicit workflow, then post straight-line depreciation within controlled accounting periods.</p><ul><li>Componentized acquisition records</li><li>Useful life and residual value controls</li><li>Carrying values and disposal outcomes</li></ul><a href="#section-features-detail">Explore asset features <ArrowRight size={16}/></a></div><div className="feature-visual finance-visual"><div className="ledger-card"><div className="ledger-heading"><span>PERIOD CLOSE</span><span className="ledger-status"> -  READY FOR REVIEW</span></div><h3>Depreciation summary</h3><div className="ledger-total"><span>Sample period charge</span><b>₦12,480,000</b></div><div className="ledger-line"><span>Plant & equipment</span><b>₦7,840,000</b></div><div className="ledger-line"><span>Vehicles</span><b>₦3,360,000</b></div><div className="ledger-line"><span>Office equipment</span><b>₦1,280,000</b></div><small>Fictional values for product illustration</small></div><div className="visual-caption">Financial workflows · Fictional values</div></div></div>
        <div id="section-features-detail" className="feature-row feature-row-reverse"><div className="feature-copy"><p className="section-kicker">CUSTODY, MOVEMENT & CARE</p><h2>Know where an asset is - and who is responsible.</h2><p>Connect people, departments and locations to controlled assignments, transfers and maintenance history without silently changing accounting records.</p><ul><li>Custodian and location records</li><li>Controlled transfers with history</li><li>Maintenance plans, work orders and costs</li></ul><a href="#demo">See a fictional asset register <ArrowRight size={16}/></a></div><div className="feature-visual movement-visual"><div className="asset-card"><div className="asset-card-top"><span className="asset-tag">AF-0218</span><span className="asset-state">IN SERVICE</span></div><div className="equipment-icon"><Wrench size={31}/></div><h3>Industrial generator</h3><p>Plant & equipment  -  Fictional sample</p><div className="asset-facts"><span>LOCATION<b>Workshop  -  Site B</b></span><span>CUSTODIAN<b>Operations team</b></span></div><div className="asset-timeline"><i/><div><b>Maintenance completed</b><small>Routine service  -  sample history</small></div></div></div><div className="visual-caption">Asset record · Fictional sample</div></div></div>
      </section>

      <section id="section-solutions" className="solutions-section"><div className="section-wrap"><div className="section-heading centered"><p className="section-kicker">MADE FOR THE TEAMS THAT CARE</p><h2>One record. Many people accountable.</h2><p>Useful across asset-heavy environments, with a shared record for finance, operations and assurance.</p></div><div className="solutions-grid">{[{icon:Factory,title:'Construction & engineering',text:'Track equipment, vehicles and custody across offices and project locations.'},{icon:Boxes,title:'Manufacturing & operations',text:'Connect plant records to maintenance, ownership and movement history.'},{icon:GraduationCap,title:'Education',text:'Organize equipment and facilities across departments and campuses.'},{icon:Building2,title:'Facilities & multi-location',text:'See what is assigned, where it is placed and what needs verification.'}].map(({icon:Icon,title,text})=><article key={title}><Icon/><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>

      <section id="section-how-it-works" className="section-wrap how-section"><div className="section-heading"><p className="section-kicker">A PRACTICAL START</p><h2>Set up with clarity.<br/>Operate with confidence.</h2><p>Start with a guided conversation, agree the scope and establish a clean, accountable register.</p><a className="text-link" href="#request-demo">Talk through your rollout <ArrowRight size={16}/></a></div><div className="steps-list">{[['01','Discover','Review asset classes, locations, users and accounting conventions.'],['02','Configure','Set up the workspace, structure and access with your administrator.'],['03','Manage','Record assets and changes through explicit lifecycle workflows.'],['04','Verify & report','Review physical observations, findings and durable report snapshots.']].map(([n,title,text])=><article key={n}><span>{n}</span><div><h3>{title}</h3><p>{text}</p></div></article>)}</div></section>

      <section id="section-security" className="security-band"><div className="security-inner"><div><p className="section-kicker">CONTROL IS BUILT INTO THE WORKFLOW</p><h2>Clear boundaries.<br/>Traceable actions.</h2><p>AssetFlow enforces organization-scoped data access, role-aware permissions and controlled lifecycle transitions. Private verification evidence is available through authenticated access.</p><a href="#section-security-detail">Review security controls <ArrowRight size={16}/></a></div><div className="security-points">{['Organization-scoped authorization','Role-aware workflows and approvals','Application audit history','Authenticated private evidence'].map(text=><div key={text}><span><Check size={14} aria-hidden="true" /></span>{text}</div>)}</div></div><div id="section-security-detail" className="security-note">Deployment practices, backups, retention and operational assurances depend on the hosting environment. AssetFlow does not claim an independent security certification.</div></section>

      <section id="section-pricing" className="pricing-section"><div className="pricing-inner"><div><p className="section-kicker">PRICING & ONBOARDING</p><h2>A plan shaped around your operation.</h2><p>Commercial pricing is agreed after discovery. Discuss users, asset volume, locations, hosting and support with our team.</p></div><div className="pricing-actions"><span>Managed onboarding and guided setup</span><span>Self-service trial when enabled by the service</span><a className="button-primary" href={mockMode && !authenticated ? '#request-demo' : '#get-started'}>{mockMode && !authenticated ? 'Request pricing' : 'Get started'}<ArrowRight size={16}/></a></div></div></section>

      <section className="closing-cta"><p>BRING EVERY ASSET INTO FOCUS</p><h2>Make your asset records<br/>work harder for your team.</h2><div><a className="button-light" href="#request-demo">Request a demo <ArrowRight size={16}/></a><a className="closing-link" href="#section-features">Explore features</a></div></section>
    </main>
    <PublicFooter sections authenticated={authenticated} workspaceRoute={workspaceRoute} />
  </div>;
}
