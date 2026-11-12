import {useEffect,useState} from 'react';
import {NavLink,Route,Routes,useLocation,useNavigate} from 'react-router-dom';
import {Activity,AlertTriangle,ArrowDownLeft,ArrowUpRight,BriefcaseBusiness,Check,CheckCircle2,ChevronRight,ChartNoAxesCombined,FileCheck2,FileText,LayoutDashboard,LogOut,Menu,Receipt,Search,ShieldCheck,Users,WalletCards,Zap,LockKeyhole,Workflow,Command,Play,PanelLeftClose,PanelLeftOpen,X,Keyboard,LifeBuoy} from 'lucide-react';
import type {LucideIcon} from 'lucide-react';
import {api,token} from './lib/api';
import {Dashboard,Customers,Transactions,Refunds,Disputes,Reviews,Audit,Evidence,RootCause,Login,Agreements,Milestones} from './pages/Pages';
import ExecutionTimeline from './pages/ExecutionTimeline';
import FinancialLifecycle from './pages/FinancialLifecycle';
import Proof from './pages/Proof';
import {StorefrontAdmin,StorefrontPage} from './pages/Storefront';

const nav=[['Overview','/',LayoutDashboard],['Customer intelligence','/customers',Users],['Review lab','/reviews',Search],['Transactions','/transactions',WalletCards],['Execution timeline','/execution',Workflow],['Refund investigations','/refunds',ArrowDownLeft],['Dispute center','/disputes',AlertTriangle],['Evidence vault','/evidence',FileCheck2],['Root-cause intelligence','/root-cause',ChartNoAxesCombined],['Trust & audit','/audit',ShieldCheck]] as const;

function ProductPreview(){
  const [tab,setTab]=useState(0);
  const steps=[
    {label:'Understand',title:'See the whole customer picture',desc:'Connect orders, feedback and operational history in one investigation view.',code:['customer = merchant.customers.get("C-2048")','history = intelligence.timeline(customer)','signals = reviews.cluster(history)'],status:'Customer context assembled'},
    {label:'Resolve',title:'Move from signal to action',desc:'Investigate refunds and disputes with evidence, clear status and human approval.',code:['case = disputes.assess("DP-7821")','evidence = vault.attach(case, files)','approval = merchant.review(case)'],status:'Awaiting merchant approval'},
    {label:'Verify',title:'Keep every decision accountable',desc:'Track provider-confirmed outcomes and preserve an auditable record of what happened.',code:['result = paypal.fetch_authoritative_status()','audit.record(actor, action, result)','case.close(when=result.is_final)'],status:'Audit trail recorded'}
  ];
  return <div className="preview-shell" aria-label="Illustrative MerchantOS dashboard preview">
    <div className="preview-top"><div className="window-dots"><i/><i/><i/></div><span>MERCHANTOS / COMMAND CENTER</span><span className="preview-live"><i/> DEMO ENVIRONMENT</span></div>
    <div className="preview-app">
      <aside className="preview-rail"><div className="mini-brand">M</div><div className="rail-icon active"><LayoutDashboard size={15}/></div><div className="rail-icon"><Users size={15}/></div><div className="rail-icon"><WalletCards size={15}/></div><div className="rail-icon"><ShieldCheck size={15}/></div></aside>
      <div className="preview-main">
        <div className="preview-heading"><div><small>MONDAY, 10 NOVEMBER</small><h3>Good morning, Alex.</h3><p>Your commerce operations at a glance.</p></div><span className="preview-pill">Sandbox data</span></div>
        <div className="preview-metrics"><div><small>ORDERS REVIEWED</small><b>1,284</b><em>Across connected records</em></div><div><small>OPEN DISPUTES</small><b>08</b><em className="amber">Needs attention</em></div><div><small>REFUND VALUE</small><b>$2,460</b><em>Recorded activity</em></div></div>
        <div className="preview-lower"><div className="preview-chart"><div className="mini-panel-head"><b>Operational pulse</b><span>Last 7 days</span></div><div className="chart-bars"><i style={{height:'36%'}}/><i style={{height:'54%'}}/><i style={{height:'43%'}}/><i style={{height:'72%'}}/><i style={{height:'61%'}}/><i style={{height:'84%'}}/><i style={{height:'68%'}}/></div><div className="chart-labels"><span>MON</span><span>TUE</span><span>WED</span><span>THU</span><span>FRI</span><span>SAT</span><span>SUN</span></div></div>
          <div className="preview-queue"><div className="mini-panel-head"><b>Needs review</b><span>03 items</span></div><div className="queue-row"><i className="queue-dot red"/><span><b>Dispute response</b><small>Evidence due soon</small></span><ChevronRight size={13}/></div><div className="queue-row"><i className="queue-dot gold"/><span><b>Refund proposal</b><small>Approval required</small></span><ChevronRight size={13}/></div><div className="queue-row"><i className="queue-dot green"/><span><b>Agreement milestone</b><small>Evidence submitted</small></span><ChevronRight size={13}/></div></div></div>
        <div className="preview-disclaimer">Illustrative interface · sample values, not live merchant data</div>
      </div>
    </div>
    <div className="preview-caption"><span>01 / PRODUCT PREVIEW</span><span>Built around real operational workflows <ArrowUpRight size={13}/></span></div>
    <div className="preview-tabs" role="tablist" aria-label="MerchantOS workflow stages">{steps.map((s,i)=><button type="button" role="tab" id={`workflow-tab-${i}`} aria-selected={tab===i} aria-controls="workflow-panel" tabIndex={tab===i?0:-1} key={s.label} onClick={()=>setTab(i)} onKeyDown={(e:any)=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=(i+(e.key==='ArrowRight'?1:-1)+steps.length)%steps.length;setTab(next);document.getElementById(`workflow-tab-${next}`)?.focus();}}} className={tab===i?'selected':''}><span>0{i+1}</span>{s.label}</button>)}</div>
    <div className="workflow-detail" id="workflow-panel" role="tabpanel" aria-labelledby={`workflow-tab-${tab}`}><div><span className="eyebrow">WORKFLOW / 0{tab+1}</span><h3>{steps[tab].title}</h3><p>{steps[tab].desc}</p></div><div className="code-window"><div className="code-head"><span><i/> workflow.ts</span><span aria-live="polite">{steps[tab].status}</span></div><pre>{steps[tab].code.map((line,i)=><code key={line}><b>{i+1}</b>{line}</code>)}</pre></div></div>
  </div>
}

function LandingPage({onLogin}:{onLogin:()=>void}){
  const [mobileOpen,setMobileOpen]=useState(false);
  const jump=(id:string)=>{document.getElementById(id)?.scrollIntoView({behavior:'smooth'});setMobileOpen(false);};
  return <div className="marketing">
    <a className="skip-link" href="#main-content">Skip to content</a><header className="site-nav"><a className="site-brand" href="#top" onClick={e=>{e.preventDefault();window.scrollTo({top:0,behavior:'smooth'});}}><span className="site-mark">M</span><span>merchant<span className="brand-os">OS</span></span></a><button type="button" className="mobile-menu" onClick={()=>setMobileOpen(!mobileOpen)} aria-label="Toggle navigation" aria-expanded={mobileOpen} aria-controls="marketing-navigation"><Menu size={19}/></button><nav id="marketing-navigation" className={mobileOpen?'open':''} aria-label="Main navigation"><button onClick={()=>jump('platform')}>Platform</button><button onClick={()=>jump('workflows')}>Workflows</button><button onClick={()=>jump('trust')}>Trust</button><button onClick={()=>jump('plans')}>Plans</button><button className="nav-login" onClick={onLogin}>Sign in <ArrowUpRight size={14}/></button></nav></header>
    <main id="main-content">
      <section className="hero-section"><div className="hero-gridline"/><div className="hero-copy"><div className="kicker"><span/> COMMERCE OPERATIONS, CONNECTED</div><h1>Run commerce.<br/><em>See what matters.</em></h1><p className="hero-lede">The intelligence layer for customer context, payment operations and merchant trust — in one considered workspace.</p><div className="hero-actions"><button className="cta-primary" onClick={onLogin}>Explore the workspace <ArrowUpRight size={16}/></button><button className="cta-secondary" onClick={()=>jump('platform')}><Play size={14}/> See how it works</button></div><div className="hero-proof"><span><Check size={13}/> Human-approved actions</span><span><Check size={13}/> Provider-verified payment state</span><span><Check size={13}/> Traceable decisions</span></div></div><div className="hero-visual"><div className="visual-orbit orbit-one"/><div className="visual-orbit orbit-two"/><div className="hero-index">FIG. 01 <span>MERCHANT OPERATING SYSTEM</span></div><ProductPreview/></div><div className="hero-foot"><span>DESIGNED FOR THE MOMENTS THAT MATTER</span><span>SCROLL TO EXPLORE ↓</span></div></section>
      <section className="trust-strip" id="trust"><div className="trust-intro"><span className="eyebrow">A BETTER OPERATING STANDARD</span><p>Clarity before action.<br/><b>Evidence after every decision.</b></p></div><div className="trust-principles"><div><ShieldCheck/><span><b>Trust by design</b><small>Permission-aware workflows</small></span></div><div><Workflow/><span><b>Connected context</b><small>Customer to transaction</small></span></div><div><LockKeyhole/><span><b>Human control</b><small>Consequential actions stay reviewable</small></span></div></div></section>
      <section className="platform-section section-pad" id="platform"><div className="section-topline"><span>01 / THE PLATFORM</span><span>ONE WORKSPACE. CONNECTED SIGNALS.</span></div><div className="section-intro"><h2>Less switching.<br/><em>More understanding.</em></h2><p>MerchantOS brings fragmented operational signals into a coherent picture, so teams can investigate confidently and act with context.</p></div><div className="capability-layout"><article className="capability-main"><div className="capability-art"><div className="orbit-core"><Command size={28}/></div><div className="orbit-node node-a"><Users size={17}/><span>Customer</span></div><div className="orbit-node node-b"><Receipt size={17}/><span>Payments</span></div><div className="orbit-node node-c"><FileCheck2 size={17}/><span>Evidence</span></div><div className="orbit-node node-d"><Activity size={17}/><span>Signals</span></div><div className="orbit-line"/></div><div className="capability-copy"><span className="eyebrow">THE INTELLIGENCE LAYER</span><h3>One connected view of the business.</h3><p>Bring customer history, reviews, transactions and operational events together to understand what happened — and what deserves attention.</p></div></article><div className="capability-list"><article><span>01</span><div><Users/><h3>Customer intelligence</h3><p>Investigate history, feedback and related orders in context.</p></div><ArrowUpRight/></article><article><span>02</span><div><WalletCards/><h3>Payment operations</h3><p>Review transactions, refund activity and provider status.</p></div><ArrowUpRight/></article><article><span>03</span><div><AlertTriangle/><h3>Dispute management</h3><p>Organize cases, evidence and response workflows.</p></div><ArrowUpRight/></article><article><span>04</span><div><FileText/><h3>Agreements & milestones</h3><p>Track commitments, deliverables and approvals.</p></div><ArrowUpRight/></article></div></div></section>
      <section className="workflow-section section-pad" id="workflows"><div className="section-topline"><span>02 / HOW IT WORKS</span><span>FROM SIGNAL TO VERIFIED OUTCOME</span></div><div className="workflow-head"><h2>Every decision has<br/><em>a clear next step.</em></h2><p>Designed to make operational work easier to follow — without hiding the human decisions that matter.</p></div><div className="workflow-steps"><article><span className="step-no">01</span><div className="step-icon"><Search/></div><h3>Understand</h3><p>Bring the relevant customer, order and feedback history into view.</p><span className="step-foot">CONTEXT, NOT GUESSWORK</span></article><article><span className="step-no">02</span><div className="step-icon"><Zap/></div><h3>Investigate</h3><p>Assess refunds, disputes and agreements with supporting evidence.</p><span className="step-foot">EVIDENCE BEFORE ACTION</span></article><article><span className="step-no">03</span><div className="step-icon"><CheckCircle2/></div><h3>Verify</h3><p>Confirm outcomes against authoritative records and preserve the audit trail.</p><span className="step-foot">TRACEABLE BY DEFAULT</span></article></div></section>
      <section className="trust-section section-pad"><div className="trust-visual"><div className="trust-stamp"><ShieldCheck size={36}/><span>BUILT AROUND<br/>ACCOUNTABILITY</span></div><div className="trust-lines"><span>01 / INTERPRET</span><span>02 / VALIDATE</span><span>03 / AUTHORIZE</span><span>04 / RECORD</span></div></div><div className="trust-copy"><div className="section-topline"><span>03 / TRUST & CONTROL</span><span>THE MERCHANT STAYS IN CONTROL</span></div><h2>Intelligence can advise.<br/><em>People stay in charge.</em></h2><p>MerchantOS is designed around a clear separation between insight and authority. AI can help interpret information; deterministic checks and provider responses establish operational truth; consequential actions remain subject to merchant control.</p><ul><li><Check/> Deterministic validation for critical states</li><li><Check/> Explicit approval for consequential actions</li><li><Check/> Audit history for operational accountability</li><li><Check/> Clear distinction between demo and provider data</li></ul></div></section>
      <section className="plans-section section-pad" id="plans"><div className="section-topline"><span>04 / PILOT PATHS</span><span>CONTROLLED PILOT RELEASE</span></div><div className="plans-head"><h2>Evaluate with care.<br/><em>Deploy with evidence.</em></h2><p>MerchantOS is currently a single-merchant pilot. Public pricing and self-serve multi-merchant onboarding are not available in this release.</p></div><div className="plan-grid"><article className="plan-card"><span className="plan-tag">01 / EVALUATE</span><h3>Sandbox</h3><p>Explore core workflows with demo data and a safe environment.</p><ul><li><Check/> Product walkthrough</li><li><Check/> Sample operational records</li><li><Check/> Core workflow exploration</li></ul><button onClick={onLogin}>Open workspace <ArrowUpRight size={14}/></button></article><article className="plan-card plan-featured"><span className="plan-tag">02 / TEST</span><div className="recommended">PAYPAL SANDBOX</div><h3>Payment validation</h3><p>Evaluate the refund workflow against PayPal Sandbox, with merchant approval at each consequential step.</p><ul><li><Check/> Sandbox checkout and capture</li><li><Check/> Refund proposal and approval</li><li><Check/> Provider-confirmed outcome</li></ul><button onClick={onLogin}>Sign in to evaluate <ArrowUpRight size={14}/></button></article><article className="plan-card"><span className="plan-tag">03 / PLAN</span><h3>Deployment review</h3><p>Understand the engineering and governance work required before a production rollout.</p><ul><li><Check/> Tenant-isolation requirements</li><li><Check/> Credential and webhook controls</li><li><Check/> Production-readiness gaps</li></ul><button onClick={()=>jump('trust')}>Review controls <ArrowUpRight size={14}/></button></article></div><p className="plans-note">Pilot prototype only. Public pricing, general availability and multi-merchant production onboarding are not offered in this release.</p></section>
      <section className="closing-cta"><div><span className="eyebrow">A CLEARER WAY TO OPERATE</span><h2>Make every signal<br/><em>count.</em></h2></div><button className="cta-primary" onClick={onLogin}>Enter MerchantOS <ArrowUpRight size={16}/></button><div className="closing-mark">M</div></section>
    </main>
    <footer className="site-footer"><a className="site-brand" href="#top"><span className="site-mark">M</span><span>merchant<span className="brand-os">OS</span></span></a><span className="footer-copy">COMMERCE INTELLIGENCE, WITH ACCOUNTABILITY.</span><div><button onClick={()=>jump('platform')}>Platform</button><button onClick={()=>jump('trust')}>Trust</button><button onClick={onLogin}>Sign in</button></div><small>© 2026 MerchantOS. Product preview uses illustrative sample data.</small></footer>
  </div>
}

type NavItem = readonly [string,string,LucideIcon];
const navGroups: {label:string;items:readonly NavItem[]}[] = [
  { label: 'STORE WORKFLOW', items: [
    ['Store','/storefront',Receipt],
    ['Reviews','/reviews',Search],
    ['Complaints','/disputes',AlertTriangle],
    ['Evidence','/evidence',FileCheck2],
    ['Actions','/execution',Workflow],
    ['Profit & loss','/financial-operations',WalletCards]
  ]},
  { label: 'OTHER WORKSPACE', items: [
    ['Overview','/',LayoutDashboard],
    ['Customer intelligence','/customers',Users],
    ['Root-cause intelligence','/root-cause',ChartNoAxesCombined],
    ['Transactions','/transactions',WalletCards],
    ['Refund investigations','/refunds',ArrowDownLeft],
    ['Proof & status','/proof',ShieldCheck],
    ['Agreements','/agreements',FileText],
    ['Milestones','/milestones',BriefcaseBusiness],
    ['Trust & audit','/audit',ShieldCheck]
  ]}
] as const;
const allNav: NavItem[] = navGroups.flatMap(group => [...group.items]);

export default function App(){
  const [authed,setAuthed]=useState(!!token());
  const [user,setUser]=useState<any>(null);
  const [health,setHealth]=useState<any>(null);
  const [collapsed,setCollapsed]=useState(false);
  const [mobileOpen,setMobileOpen]=useState(false);
  const [showLogin,setShowLogin]=useState(false);
  const [quickOpen,setQuickOpen]=useState(false);
  const [quickQuery,setQuickQuery]=useState('');
  const navTo=useNavigate();
  const location=useLocation();
  const activeRoute=navGroups.flatMap(group=>group.items).find(item=>item[1]===location.pathname);
  const currentPage=location.pathname==='/'?'Command center':(activeRoute?.[0]||'Merchant workspace');
  const currentSection=navGroups.find(group=>group.items.some(item=>item[1]===location.pathname))?.label||'WORKSPACE';
  useEffect(()=>{
    api('/api/health').then(x=>setHealth(x)).catch(()=>setHealth(null));
    if(token()) api('/api/auth/me').then(x=>setUser(x)).catch(()=>{
      localStorage.removeItem('merchantos_token');setAuthed(false);
    });
  },[]);
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){
        event.preventDefault();setQuickOpen(value=>!value);setQuickQuery('');
      }
      if(event.key==='Escape'){setQuickOpen(false);setMobileOpen(false);}
    };
    window.addEventListener('keydown',onKey);
    return()=>window.removeEventListener('keydown',onKey);
  },[]);
  if(location.pathname.startsWith('/store/')) return <StorefrontPage/>;
  if(!authed){
    if(showLogin)return <Login onLogin={u=>{setUser(u);setAuthed(true);setShowLogin(false);}}/>;
    return <LandingPage onLogin={()=>setShowLogin(true)}/>;
  }
  const closeMobile=()=>setMobileOpen(false);
  const signOut=()=>{
    localStorage.removeItem('merchantos_token');setAuthed(false);setUser(null);setShowLogin(false);setMobileOpen(false);navTo('/');
  };
  const quickMatches=allNav.filter(([label,path])=>`${label} ${path}`.toLowerCase().includes(quickQuery.toLowerCase()));
  return <div className={`shell ${collapsed?'collapsed':''} ${mobileOpen?'mobile-open':''}`}>
    <a className="workspace-skip" href="#workspace-main">Skip to workspace</a>
    {mobileOpen&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={closeMobile}/>}
    <aside className="sidebar" aria-label="MerchantOS navigation">
      <div className="brand-row">
        <a className="brand" href="/" onClick={e=>{e.preventDefault();navTo('/');closeMobile();}} aria-label="MerchantOS overview">
          <div className="brand-mark">M</div><div className="brand-copy"><b>MerchantOS</b><small>COMMERCE INTELLIGENCE</small></div>
        </a>
        <button className="sidebar-toggle" onClick={()=>setCollapsed(v=>!v)} aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} title={collapsed?'Expand sidebar':'Collapse sidebar'}>{collapsed?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>}</button>
        <button className="mobile-close" onClick={closeMobile} aria-label="Close navigation"><X size={18}/></button>
      </div>
      <div className="workspace-switcher"><span className="workspace-avatar">{(user?.tenant_name||'M')[0].toUpperCase()}</span><span className="workspace-meta"><b>{user?.tenant_name||'Merchant workspace'}</b><small>Single-merchant pilot</small></span><span className="workspace-caret">⌄</span></div>
      <nav className="sidebar-nav">
        {navGroups.map(group=><div className="nav-group" key={group.label}><div className="nav-group-label">{group.label}</div>{group.items.map(([label,path,Icon])=><NavLink key={label} to={path} end={path==='/'} title={collapsed?label:undefined} onClick={closeMobile} className={({isActive})=>`nav-item ${isActive?'active':''}`}><Icon size={17} strokeWidth={1.8}/><span>{label}</span></NavLink>)}</div>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-help"><LifeBuoy size={16}/><span>Operational support</span><ArrowUpRight size={13}/></div>
        <div className="user-chip"><div className="avatar">{(user?.name||'M')[0].toUpperCase()}</div><div className="user-meta"><b>{user?.name||'Merchant'}</b><small>{user?.role||'OWNER'}</small></div><button title="Sign out" aria-label="Sign out" onClick={signOut}><LogOut size={16}/></button></div>
        <small className="version">MERCHANTOS · CONTROLLED PILOT</small>
      </div>
    </aside>
    <main className="main" id="workspace-main">
      <header className="topbar">
        <div className="topbar-title"><button className="mobile-menu-trigger" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Menu size={19}/></button><div><span className="eyebrow">{currentSection} / MERCHANT WORKSPACE</span><h2>{currentPage}</h2></div></div>
        <div className="top-actions">
          <button className="global-search" onClick={()=>{setQuickOpen(true);setQuickQuery('');}} aria-label="Open quick navigation"><Search size={15}/><span>Find a workspace</span><kbd>⌘ K</kbd></button>
          <span className="env"><i/> Sandbox / Demo data</span><div className="avatar top-avatar" aria-label={`Signed in as ${user?.name||'Merchant'}`}>{(user?.name||'M')[0].toUpperCase()}</div>
        </div>
      </header>
      <div className="global-pipeline" aria-label="Operational pipeline"><span>Reviews</span><b>→</b><span>AI</span><b>→</b><span>Grid</span><b>→</b><span>Approval</span><b>→</b><span>PayPal</span><b>→</b><span>Audit</span><a href="/proof" onClick={e=>{e.preventDefault();navTo('/proof')}}>Proof ↗</a><small>{health?.environment==='Sandbox'?'PayPal Sandbox · live money blocked':'PayPal environment unconfirmed'} · Render · {health?.commit||'commit unknown'} · {health?.uptime_seconds==null?'uptime unknown':`${health.uptime_seconds}s`} · AI: computed / llm when configured</small></div><div className="content"><Routes><Route path="/" element={<Dashboard/>}/><Route path="/customers" element={<Customers/>}/><Route path="/reviews" element={<Reviews/>}/><Route path="/root-cause" element={<RootCause/>}/><Route path="/transactions" element={<Transactions/>}/><Route path="/execution" element={<ExecutionTimeline/>}/><Route path="/financial-operations" element={<FinancialLifecycle/>}/><Route path="/storefront" element={<StorefrontAdmin/>}/><Route path="/proof" element={<Proof/>}/><Route path="/agreements" element={<Agreements/>}/><Route path="/milestones" element={<Milestones/>}/><Route path="/refunds" element={<Refunds/>}/><Route path="/disputes" element={<Disputes/>}/><Route path="/evidence" element={<Evidence/>}/><Route path="/audit" element={<Audit/>}/><Route path="*" element={<Dashboard/>}/></Routes></div>
    </main>
    {quickOpen&&<div className="quick-overlay" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setQuickOpen(false);}}><section className="quick-dialog" role="dialog" aria-modal="true" aria-labelledby="quick-title"><div className="quick-input-row"><Search size={18}/><label className="sr-only" id="quick-title" htmlFor="quick-search">Find a workspace</label><input id="quick-search" autoFocus placeholder="Search pages and workflows…" value={quickQuery} onChange={e=>setQuickQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&quickMatches[0]){navTo(quickMatches[0][1]);setQuickOpen(false);}}}/><kbd>ESC</kbd></div><div className="quick-results">{quickMatches.map(([label,path,Icon])=><button key={path} onClick={()=>{navTo(path);setQuickOpen(false);}}><Icon size={17}/><span>{label}</span><small>{path==='/'?'Overview':path}</small><ChevronRight size={14}/></button>)}{!quickMatches.length&&<p>No matching workspace pages.</p>}</div><footer><span><Keyboard size={13}/> Navigate with search</span><span>ENTER to open</span></footer></section></div>}
  </div>;
}
