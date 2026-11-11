import {useEffect,useState} from 'react';
import {AgGridProvider,AgGridReact} from 'ag-grid-react';
import {AllCommunityModule,themeQuartz} from 'ag-grid-community';
import type {ColDef} from 'ag-grid-community';
import {api,money} from '../lib/api';
import {Activity,AlertCircle,ArrowUpRight,CheckCircle2,Clock3,FileText,RefreshCw,Search,ShieldCheck,UploadCloud,Users,Wallet} from 'lucide-react';

type Any=Record<string,any>;

function useLoad<T=any>(path:string){
  const [data,setData]=useState<T|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(true);

  const load=()=>{
    setBusy(true);
    api<T>(path)
      .then(setData)
      .catch(e=>setError(e.message))
      .finally(()=>setBusy(false));
  };

  useEffect(load,[path]);
  return {data,error,busy,refresh:load};
}

function Heading({title,sub,action}:{title:string,sub:string,action?:any}){
  return <div className="page-heading">
    <div><h1>{title}</h1><p>{sub}</p></div>
    {action}
  </div>;
}

function Panel({title,children,extra}:{title:string,children:any,extra?:any}){
  return <section className="panel">
    <div className="panel-head"><h3>{title}</h3>{extra}</div>
    {children}
  </section>;
}

function Table({columns,rows,empty='No records available'}:{columns:string[],rows:any[],empty?:string}){
  return <div className="table-wrap">
    <table>
      <thead><tr>{columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {rows.length
          ? rows.map((r,i)=><tr key={r.id||i}>
              {columns.map(c=><td key={c}>{r[c]??'—'}</td>)}
            </tr>)
          : <tr><td colSpan={columns.length} className="empty">{empty}</td></tr>}
      </tbody>
    </table>
  </div>;
}

function Metric({label,value,caption,icon:Icon}:any){
  return <div className="metric">
    <div className="metric-top"><span>{label}</span><Icon size={18}/></div>
    <strong>{value??'—'}</strong>
    <small>{caption}</small>
  </div>;
}

/* LOGIN AND FIRST OWNER REGISTRATION */

export function Login({onLogin}:{onLogin:(u:any)=>void}) {
  const [email,setEmail]=useState('');
  const [password,setPassword]=useState('');
  const [tenant,setTenant]=useState('Demo Store');
  const [name,setName]=useState('Store Owner');
  const [bootstrap,setBootstrap]=useState('');
  const [mode,setMode]=useState<'login'|'register'>('login');
  const [err,setErr]=useState('');
  const [busy,setBusy]=useState(false);

  async function submit(e:any) {
    e.preventDefault();
    setBusy(true);
    setErr('');

    try {
      const registering=mode==='register';

      const r=await api<any>(
        registering?'/api/auth/register':'/api/auth/login',
        {
          method:'POST',
          headers:registering
            ? {'X-MerchantOS-Bootstrap-Token':bootstrap}
            : undefined,
          body:JSON.stringify(
            registering
              ? {email,password,tenant_name:tenant,name}
              : {email,password}
          )
        }
      );

      setBootstrap('');
      localStorage.setItem('merchantos_token',r.access_token);
      onLogin(r.user);

    } catch(e:any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <b>MerchantOS</b>
            <small>INTELLIGENT COMMERCE & TRUST</small>
          </div>
        </div>

        <h1>
          {mode==='login'?'Welcome back':'Create your pilot account'}
        </h1>

        <p>Secure access to your merchant operations.</p>

        <form onSubmit={submit}>
          {mode==='register' && <>
            <label>
              Your name
              <input
                value={name}
                onChange={e=>setName(e.target.value)}
                required
              />
            </label>

            <label>
              Business name
              <input
                value={tenant}
                onChange={e=>setTenant(e.target.value)}
                required
              />
            </label>

            <label>
              One-time bootstrap token
              <input
                type="password"
                value={bootstrap}
                onChange={e=>setBootstrap(e.target.value)}
                autoComplete="off"
                minLength={32}
                required
              />
            </label>
          </>}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={e=>setEmail(e.target.value)}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={e=>setPassword(e.target.value)}
              required
              minLength={12}
            />
          </label>

          {err && <div className="error">{err}</div>}

          <button className="primary full" disabled={busy}>
            {busy?'Please wait…':
              mode==='login'?'Sign in':'Create account'}
          </button>
        </form>

        <button
          className="link-button"
          onClick={()=>{
            setErr('');
            setBootstrap('');
            setMode(mode==='login'?'register':'login');
          }}
        >
          {mode==='login'
            ?'Create the pilot account'
            :'Already registered? Sign in'}
        </button>

        <div className="demo-note">
          This release is configured for a single-merchant pilot.
          Additional workspaces remain disabled until tenant isolation
          is complete.
        </div>
      </div>
    </div>
  );
}

/* COMMAND CENTER */

export function Dashboard(){
  const {data,error,busy,refresh}=useLoad<Any>('/api/dashboard');
  const {data:ins}=useLoad<Any>('/api/insights');
  const {data:root}=useLoad<Any>('/api/root-cause');

  const findings=root?.findings||ins?.findings||[];

  function formatFinding(item:any){
    let details=item.summary||item.description||item.detail||{};

    if(typeof details==='string'){
      try{
        details=JSON.parse(details);
      }catch{
        details={description:details};
      }
    }

    if(typeof details!=='object'||details===null){
      details={description:String(details)};
    }

    const category=String(
      item.category||details.category||item.title||'Operational issue'
    ).replace(/_/g,' ');

    const title=category.replace(/\b\w/g,c=>c.toUpperCase());

    const batch=item.batch_id||details.batch;
    const complaints=item.count??details.complaints;
    const share=item.share_pct??details.share_pct;

    return {
      title,
      batch,
      complaints,
      share,
      description:details.description||details.summary
    };
  }

  return <>
    <Heading
      title="Command center"
      sub="A live view of customer experience, financial operations and emerging business issues."
      action={
        <button className="secondary" onClick={refresh}>
          <RefreshCw size={15}/> Refresh
        </button>
      }
    />

    {error&&<div className="error">{error}</div>}

    <div className="metric-grid">
      <Metric
        label="Orders"
        value={data?.orders}
        caption="Recorded merchant orders"
        icon={Wallet}
      />

      <Metric
        label="Customer reviews"
        value={data?.reviews}
        caption="Imported feedback records"
        icon={Users}
      />

      <Metric
        label="Open disputes"
        value={data?.disputes}
        caption="Requires merchant attention"
        icon={AlertCircle}
      />

      <Metric
        label="Refund value"
        value={data?.refund_total!==undefined?money(data.refund_total):'—'}
        caption="Recorded refund activity"
        icon={Activity}
      />
    </div>

    <div className="two-col">
      <Panel
        title="Operational intelligence"
        extra={<span className="muted">{findings.length} findings</span>}
      >
        <div className="insight-list">
          {findings.slice(0,6).map((item:any,index:number)=>{
            const f=formatFinding(item);

            return (
              <article className="insight" key={item.id||index}>
                <span className="insight-icon">
                  <AlertCircle size={17}/>
                </span>

                <div>
                  <b>{f.title}</b>

                  {f.batch&&(
                    <p>Production batch: <strong>{f.batch}</strong></p>
                  )}

                  {f.complaints!==undefined&&(
                    <p>
                      <strong>{f.complaints}</strong> customer complaints
                    </p>
                  )}

                  {f.share!==undefined&&(
                    <p>
                      <strong>{f.share}%</strong> of reported complaints
                    </p>
                  )}

                  {f.description&&(
                    <p>{f.description}</p>
                  )}
                </div>
              </article>
            );
          })}

          {!findings.length&&(
            <p className="muted">
              {busy?'Loading intelligence…':'No findings available yet.'}
            </p>
          )}
        </div>
      </Panel>

      <Panel title="Control principles">
        <div className="principles">
          <p><CheckCircle2/> AI interprets; deterministic systems validate.</p>
          <p><CheckCircle2/> Humans authorize consequential actions.</p>
          <p><CheckCircle2/> PayPal responses determine payment truth.</p>
          <p><CheckCircle2/> Audit history records what happened.</p>
        </div>
      </Panel>
    </div>
  </>;
}
/* CUSTOMERS */

export function Customers(){
  const {data,error,busy}=useLoad<any[]>('/api/customers');
  const [q,setQ]=useState('');
  const [detail,setDetail]=useState<any>(null);

  const rows=(data||[])
    .filter(x=>JSON.stringify(x).toLowerCase().includes(q.toLowerCase()))
    .map(x=>({
      ...x,
      customer_id:<button className="table-link" onClick={async()=>{
        try{
          setDetail(await api(`/api/customers/${encodeURIComponent(x.customer_id)}`));
        }catch(e:any){
          setDetail({error:e.message});
        }
      }}>{x.customer_id}</button>
    }));

  return <>
    <Heading title="Customer intelligence" sub="Investigate customer history, feedback, associated orders and recorded resolutions."/>
    <div className="toolbar">
      <div className="search">
        <Search size={16}/>
        <input placeholder="Search customer or reference…" value={q} onChange={e=>setQ(e.target.value)}/>
      </div>
    </div>

    <Panel title="Customers">
      <Table columns={['customer_id','customer_name','review_count','referenced_orders','avg_rating','latest_review']} rows={rows.map(x=>({...x,latest_review:x.latest_review?.slice(0,10)}))}/>
      {error&&<div className="error">{error}</div>}
      {busy&&<p className="muted">Loading customers…</p>}
    </Panel>

    {detail&&<Panel title="Customer investigation"><pre>{JSON.stringify(detail,null,2)}</pre></Panel>}
  </>;
}

/* REVIEWS */

export function Reviews(){
  const {data,error,refresh}=useLoad<any[]>('/api/reviews/semantic-clusters');
  const [file,setFile]=useState<File|null>(null);
  const [msg,setMsg]=useState('');

  async function upload(){
    if(!file)return;
    const f=new FormData();
    f.append('file',file);

    try{
      const r=await api<any>('/api/reviews/import/generic_csv',{method:'POST',body:f});
      setMsg(`Imported ${r.imported??r.inserted??0} reviews. ${r.duplicates??0} duplicates skipped.`);
      refresh();
    }catch(e:any){
      setMsg(e.message);
    }
  }

  async function analyze(){
    try{
      const r=await api<any>('/api/reviews/semantic-analysis',{method:'POST'});
      setMsg(`Analysis complete using ${r.method||'configured pipeline'}.`);
      refresh();
    }catch(e:any){
      setMsg(e.message);
    }
  }

  return <>
    <Heading title="Review lab" sub="Import customer feedback, analyse complaint themes and inspect semantic clusters."/>

    <div className="two-col">
      <Panel title="Import reviews">
        <div className="upload-box">
          <UploadCloud/>
          <input type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]||null)}/>
          <button className="primary" onClick={upload} disabled={!file}>Import CSV</button>
          <small>Merchant-authorized CSV exports only. No unauthorized scraping.</small>
        </div>
      </Panel>

      <Panel title="Semantic analysis">
        <p className="muted">Run the configured embedding / similarity pipeline and refresh cluster results.</p>
        <button className="primary" onClick={analyze}>Analyse reviews</button>
        {msg&&<p className="notice">{msg}</p>}
      </Panel>
    </div>

    <Panel title="Complaint clusters">
      <Table columns={['cluster_id','count','avg_sentiment','analyzed_at']} rows={data||[]}/>
      {error&&<div className="error">{error}</div>}
    </Panel>
  </>;
}

/* TRANSACTIONS */

export function Transactions(){
  const {data,error,busy}=useLoad<any[]>('/api/transactions');
  const [id,setId]=useState('');
  const [record,setRecord]=useState<any>(null);

  const columnDefs:ColDef[]=[
    {field:'id',headerName:'Merchant order',minWidth:170,filter:true},
    {field:'customer_name',headerName:'Customer',minWidth:150,filter:true},
    {field:'product',headerName:'Product',minWidth:180,flex:1},
    {field:'amount',headerName:'Amount',minWidth:110,filter:'agNumberColumnFilter',valueFormatter:p=>p.value==null?'—':Number(p.value).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})},
    {field:'currency',headerName:'Currency',width:100},
    {field:'payment_status',headerName:'Payment state',minWidth:140,filter:true},
    {field:'capture_id',headerName:'PayPal capture',minWidth:170}
  ];

  const gridTheme=themeQuartz.withParams({
    backgroundColor:'#ffffff',
    foregroundColor:'#263329',
    accentColor:'#819b48',
    borderColor:'#e4e9df',
    headerBackgroundColor:'#f6f8f3',
    fontFamily:'DM Sans',
    fontSize:12,
    rowHoverColor:'#f7f9f4'
  });

  return <>
    <Heading title="Transaction intelligence" sub="A searchable, filterable ledger of merchant orders and provider-confirmed payment states."/>

    <div className="toolbar">
      <div className="search">
        <Search size={16}/>
        <input placeholder="Order ID" value={id} onChange={e=>setId(e.target.value)}/>
      </div>

      <button className="primary" onClick={async()=>{
        try{
          setRecord(await api(`/api/transactions/${encodeURIComponent(id)}`));
        }catch(e:any){
          setRecord({error:e.message});
        }
      }}>Investigate order</button>
    </div>

    {record&&<Panel title="Transaction record"><pre>{JSON.stringify(record,null,2)}</pre></Panel>}

    <Panel title="Recent transactions" extra={<span className="muted">{data?.length??0} records · AG Grid Community</span>}>
      {error&&<p className="error">{error}</p>}
      {busy&&<p className="muted">Loading transaction ledger…</p>}

      <div className="ag-ledger">
        <AgGridProvider modules={[AllCommunityModule]}>
          <AgGridReact
            rowData={data||[]}
            columnDefs={columnDefs}
            theme={gridTheme}
            domLayout="autoHeight"
            pagination
            paginationPageSize={10}
            paginationPageSizeSelector={[10,25,50]}
            animateRows={false}
          />
        </AgGridProvider>
      </div>

      <p className="muted">Rows are loaded from the MerchantOS transaction API. Provider-reported states remain authoritative.</p>
    </Panel>
  </>;
}

/* REFUNDS */

export function Refunds(){
  const {data,error,refresh}=useLoad<any[]>('/api/refunds');
  const [detail,setDetail]=useState<any>(null);

  const rows=(data||[]).map(x=>({
    ...x,
    id:<button className="table-link" onClick={async()=>{
      try{
        setDetail(await api(`/api/refunds/${encodeURIComponent(x.id)}`));
      }catch(e:any){
        setDetail({error:e.message});
      }
    }}>{x.id}</button>
  }));

  return <>
    <Heading title="Refund investigations" sub="Review proposals, evidence context and provider execution states. Approval remains a merchant action."/>

    <Panel title="Refund queue" extra={<button className="secondary" onClick={refresh}><RefreshCw size={14}/> Refresh</button>}>
      <Table columns={['id','order_id','amount','currency','status','paypal_status']} rows={rows}/>
      {error&&<p className="error">{error}</p>}
    </Panel>

    {detail&&<Panel title="Refund investigation"><pre>{JSON.stringify(detail,null,2)}</pre></Panel>}

    <div className="notice warning">Never interpret a submitted or pending refund as completed. Confirm the authoritative PayPal status.</div>
  </>;
}

/* DISPUTES */

export function Disputes(){
  const {data,error,refresh}=useLoad<any[]>('/api/paypal/disputes');
  const {data:local}=useLoad<any[]>('/api/disputes');
  const [detail,setDetail]=useState<any>(null);

  const paypalRows=(data||[]).map(x=>({
    ...x,
    dispute_id:<button className="table-link" onClick={async()=>{
      try{
        setDetail(await api(`/api/paypal/disputes/${encodeURIComponent(x.dispute_id)}`));
      }catch(e:any){
        setDetail({error:e.message});
      }
    }}>{x.dispute_id}</button>
  }));

  const localRows=(local||[]).map(x=>({
    ...x,
    id:<button className="table-link" onClick={async()=>{
      try{
        setDetail(await api(`/api/disputes/${encodeURIComponent(x.id)}/assessment`));
      }catch(e:any){
        setDetail({error:e.message});
      }
    }}>{x.id}</button>
  }));

  return <>
    <Heading
      title="Dispute center"
      sub="Review PayPal-synchronized disputes separately from illustrative local demo records."
      action={<button className="secondary" onClick={async()=>{
        try{
          await api('/api/paypal/disputes/sync',{method:'POST'});
          refresh();
        }catch(e:any){
          setDetail({error:e.message});
        }
      }}><RefreshCw size={15}/> Sync PayPal</button>}
    />

    <div className="two-col">
      <Panel title="PayPal disputes">
        <Table columns={['dispute_id','status','reason','lifecycle_stage','response_due_at']} rows={paypalRows}/>
        {error&&<p className="muted">{error}</p>}
      </Panel>

      <Panel title="Local illustrative disputes">
        <Table columns={['id','order_id','reason','status']} rows={localRows}/>
        <p className="muted">These are not PayPal disputes unless independently synchronized.</p>
      </Panel>
    </div>

    {detail&&<Panel title="Dispute investigation"><pre>{JSON.stringify(detail,null,2)}</pre></Panel>}
  </>;
}

/* AGREEMENTS */

export function Agreements(){
  const {data,error,refresh}=useLoad<any[]>('/api/pact/agreements');
  const [draft,setDraft]=useState('');
  const [budget,setBudget]=useState('1000');
  const [currency,setCurrency]=useState('USD');
  const [msg,setMsg]=useState('');

  async function create(){
    try{
      await api('/api/pact/agreements',{
        method:'POST',
        body:JSON.stringify({
          title:'New commercial agreement',
          description:draft,
          total_amount:budget,
          currency
        })
      });

      setDraft('');
      setMsg('Agreement draft created. Review both parties and extracted terms before approval.');
      refresh();
    }catch(e:any){
      setMsg(e.message);
    }
  }

  return <>
    <Heading title="Agreement workspace" sub="Structure commercial promises, version history, deliverables and two-party approval."/>

    <Panel title="Create agreement draft">
      <textarea value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Describe the project, deliverables, budget and expectations…"/>

      <div className="form-grid">
        <label>Total amount
          <input type="number" min="0.01" step="0.01" value={budget} onChange={e=>setBudget(e.target.value)}/>
        </label>

        <label>Currency
          <select value={currency} onChange={e=>setCurrency(e.target.value)}>
            {['USD','INR','EUR','GBP'].map(x=><option key={x}>{x}</option>)}
          </select>
        </label>
      </div>

      <button className="primary" onClick={create} disabled={!draft.trim()}>Generate agreement draft</button>
      {msg&&<p className="notice">{msg}</p>}
    </Panel>

    <Panel title="Agreements">
      <Table columns={['id','title','status','version','created_at']} rows={data||[]}/>
      {error&&<p className="error">{error}</p>}
    </Panel>
  </>;
}

/* MILESTONES */

export function Milestones(){
  const {data,error}=useLoad<any[]>('/api/pact/agreements');

  return <>
    <Heading title="Milestone workspace" sub="Track deliverables, evidence submissions, customer acceptance and payment coordination."/>
    <Panel title="Agreement milestones">
      <Table
        columns={['id','title','status','version']}
        rows={(data||[]).flatMap((a:any)=>(a.milestones||[]).map((m:any)=>({...m,agreement_id:a.id})))}
      />
      {error&&<p className="error">{error}</p>}
      <p className="muted">Milestone details are nested under their agreements in the current API.</p>
    </Panel>
  </>;
}

/* EVIDENCE */

export function Evidence(){
  const {data,error,refresh}=useLoad<any[]>('/api/evidence/files');
  const [file,setFile]=useState<File|null>(null);
  const [order,setOrder]=useState('');
  const [type,setType]=useState('DELIVERY_CONFIRMATION');
  const [description,setDescription]=useState('');

  async function upload(){
    if(!file||!order)return;
    const f=new FormData();
    f.append('file',file);

    try{
      await api(`/api/evidence/upload?order_id=${encodeURIComponent(order)}&evidence_type=${encodeURIComponent(type)}&description=${encodeURIComponent(description)}`,{
        method:'POST',
        body:f
      });
      refresh();
    }catch(e:any){
      alert(e.message);
    }
  }

  return <>
    <Heading title="Evidence vault" sub="Store merchant-provided evidence and inspect integrity."/>
    <Panel title="Register evidence file">
      <div className="form-grid">
        <label>Order ID<input value={order} onChange={e=>setOrder(e.target.value)}/></label>
        <label>Evidence type
          <select value={type} onChange={e=>setType(e.target.value)}>
            {['DELIVERY_CONFIRMATION','CUSTOMER_COMMUNICATION','PRODUCT_PHOTO','ORDER_RECORD','TEST_RESULT','SCREENSHOT','OTHER'].map(x=><option key={x}>{x}</option>)}
          </select>
        </label>
        <label>Description<input value={description} onChange={e=>setDescription(e.target.value)}/></label>
        <label>File<input type="file" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
      </div>
      <button className="primary" onClick={upload} disabled={!file||!order}>Upload evidence</button>
    </Panel>
    <Panel title="Stored evidence files">
      <Table columns={['id','original_name','mime_type','size_bytes','integrity_status','created_at']} rows={data||[]}/>
      {error&&<p className="error">{error}</p>}
      <button className="secondary" onClick={refresh}>Refresh</button>
    </Panel>
  </>;
}

/* AUDIT */

export function Audit(){
  const {data,error}=useLoad<any[]>('/api/audit');

  return <>
    <Heading title="Trust & audit" sub="A chronological record of consequential operational and financial events."/>
    <Panel title="Audit history">
      <Table
        columns={['id','event','actor','entity','detail','created_at']}
        rows={(data||[]).map(x=>({
          ...x,
          detail:typeof x.detail==='string'
            ?x.detail.slice(0,100)
            :JSON.stringify(x.detail).slice(0,100)
        }))}
      />
      {error&&<p className="error">{error}</p>}
    </Panel>
  </>;
}

/* ROOT CAUSE INTELLIGENCE */

export function RootCause(){
  const {data,error,busy,refresh}=useLoad<Any>('/api/root-cause');
  const findings=Array.isArray(data?.findings)?data.findings:[];

  return <>
    <Heading
      title="Root-cause intelligence"
      sub="Explore patterns across feedback, products and operational records."
      action={<button className="secondary" onClick={refresh}><RefreshCw size={14}/> Refresh</button>}
    />

    {error&&<div className="error">{error}</div>}

    <div className="notice warning">
      Observed associations are signals to investigate, not proof of causation.
    </div>

    <Panel title="Observed findings">
      {busy
        ? <p className="muted">Loading root-cause analysis…</p>
        : <div className="insight-list">
            {findings.map((item:any,index:number)=>
              <article className="insight" key={item.id||index}>
                <span className="insight-icon"><Activity size={16}/></span>
                <div>
                  <b>{item.title||item.category||item.product||'Operational pattern'}</b>
                  <p>{item.summary||item.description||item.detail||'Structured finding returned.'}</p>
                </div>
              </article>
            )}
            {!findings.length&&
              <div className="empty-state">
                <b>No root-cause findings yet</b>
                <p>Import feedback and run review analysis to generate findings.</p>
              </div>
            }
          </div>
      }
    </Panel>
  </>;
}
