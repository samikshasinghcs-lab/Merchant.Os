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
  const {data,error,busy,refresh}=useLoad<Any>('/api/v1/domain/dashboard');
  const {data:root}=useLoad<Any>('/api/v1/domain/root-cause');
  const [seeding,setSeeding]=useState(false);
  const [seedMessage,setSeedMessage]=useState('');

  const findings=root?.findings||[];

  async function loadIllustrativeData(){
    setSeeding(true);
    setSeedMessage('');
    try{
      const result=await api<Any>('/api/v1/domain/demo-seed',{method:'POST'});
      setSeedMessage(result.status==='ALREADY_PRESENT'
        ? 'Illustrative dataset is already present. No duplicate records were created.'
        : 'Illustrative dataset loaded. 30 linked orders; no PayPal transactions or provider confirmations were created.');
      refresh();
    }catch(e:any){
      setSeedMessage(e.message||'Could not load illustrative data.');
    }finally{
      setSeeding(false);
    }
  }

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

    const batch=item.batch||item.batch_id||details.batch;
    const complaints=item.complaints??item.count??details.complaints;
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
        <div className="heading-actions">
          <button className="secondary" onClick={refresh}>
            <RefreshCw size={15}/> Refresh
          </button>
          <button className="primary" onClick={loadIllustrativeData} disabled={seeding}>
            {seeding?'Loading…':'Load illustrative demo data'}
          </button>
        </div>
      }
    />

    {error&&<div className="error">{error}</div>}
    {seedMessage&&<div className="notice">{seedMessage}</div>}

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
  const {data,error,busy}=useLoad<any[]>('/api/v1/domain/customers');
  const [q,setQ]=useState('');
  const [detail,setDetail]=useState<any>(null);

  const rows=(data||[])
    .filter(x=>JSON.stringify(x).toLowerCase().includes(q.toLowerCase()))
    .map(x=>({
      ...x,
      customer_id:<button className="table-link" onClick={async()=>{
        try{
          setDetail(await api(`/api/v1/domain/customers/${encodeURIComponent(x.customer_id)}`));
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

    {detail && (() => {
  const customer = detail.customer || detail;
  const reviews = Array.isArray(customer.reviews)
    ? customer.reviews
    : [];

  const orders = Array.isArray(customer.orders)
    ? customer.orders
    : [];

  const averageRating = customer.avg_rating ??
    (reviews.length
      ? reviews.reduce(
          (sum: number, r: any) => sum + Number(r.rating || 0), 0
        ) / reviews.length
      : null);

  const format = (value: any) =>
    String(value ?? 'Not recorded')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());

  const date = (value: any) =>
    value
      ? new Date(value).toLocaleDateString()
      : 'Date unavailable';

  return (
    <>
      <Panel title="Customer investigation">

        <div className="customer-profile">
          <div>
            <span className="customer-avatar">
              {(customer.customer_name || '?').charAt(0).toUpperCase()}
            </span>

            <div>
              <h2>{customer.customer_name || 'Customer record'}</h2>
              <p>{customer.customer_id || 'ID unavailable'}</p>
            </div>
          </div>

          <span className="customer-status">
            Customer profile
          </span>
        </div>

        <div className="metric-grid customer-metrics">

          <Metric
            label="Reviews"
            value={reviews.length || customer.review_count || 0}
            caption="Feedback records"
            icon={FileText}
          />

          <Metric
            label="Average rating"
            value={averageRating !== null
              ? Number(averageRating).toFixed(1) + ' / 5'
              : '—'}
            caption="Customer feedback"
            icon={Activity}
          />

          <Metric
            label="Orders"
            value={orders.length || customer.referenced_orders || '—'}
            caption="Associated orders"
            icon={Wallet}
          />

          <Metric
            label="High severity"
            value={reviews.filter(
              (r: any) =>
                String(r.severity).toLowerCase() === 'high'
            ).length}
            caption="Issues requiring attention"
            icon={AlertCircle}
          />

        </div>
      </Panel>

      <Panel
        title="Customer feedback"
        extra={
          <span className="muted">
            {reviews.length} records
          </span>
        }
      >

        {reviews.length ? (

          <div className="customer-review-list">

            {reviews.map((review: any, index: number) => (

              <article
                className="customer-review"
                key={review.id || index}
              >

                <div className="customer-review-head">

                  <div>
                    <span className="review-category">
                      {format(
                        review.category ||
                        review.cluster_id ||
                        'Customer feedback'
                      )}
                    </span>

                    <small>
                      {review.id || 'Review'} · {date(review.created_at)}
                    </small>
                  </div>

                  <span className="review-rating">
                    {review.rating ?? '—'}
                    <small> / 5</small>
                  </span>

                </div>

                <p className="review-copy">
                  {review.text || 'No written feedback provided.'}
                </p>

                <div className="review-meta">

                  <span>
                    Order <b>{review.order_id || 'Not linked'}</b>
                  </span>

                  <span>
                    Product <b>{review.product || 'Not recorded'}</b>
                  </span>

                  <span className={
                    `severity-pill severity-${String(
                      review.severity || 'unknown'
                    ).toLowerCase()}`
                  }>
                    {format(review.severity || 'Unknown')} severity
                  </span>

                </div>

              </article>

            ))}

          </div>

        ) : (

          <div className="empty-state">
            <b>No feedback records</b>
            <p>No reviews were returned for this customer.</p>
          </div>

        )}

      </Panel>

      {orders.length > 0 && (

        <Panel title="Associated orders">

          <Table
            columns={[
              'id',
              'product',
              'amount',
              'currency',
              'payment_status'
            ]}
            rows={orders}
          />

        </Panel>

      )}

      <p className="customer-footnote">
        Investigation summary is based on records returned by MerchantOS.
        Missing fields are shown as not recorded.
      </p>

    </>
  );
})()}
  </>;
}

/* REVIEWS */

export function Reviews(){
  const {data,error,refresh}=useLoad<any[]>('/api/v1/domain/review-clusters');
  const [file,setFile]=useState<File|null>(null);
  const [msg,setMsg]=useState('');

  async function upload(){
    if(!file)return;
    const f=new FormData();
    f.append('file',file);

    try{
      const r=await api<any>('/api/v1/domain/reviews/import',{method:'POST',body:f});
      setMsg(`Imported ${r.imported??r.inserted??0} reviews. ${r.duplicates??0} duplicates skipped.`);
      refresh();
    }catch(e:any){
      setMsg(e.message);
    }
  }

  async function analyze(){
    try{
      const r=await api<any>('/api/v1/financial-lifecycle/complaint-clusters/run',{method:'POST'});
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

/* TRANSACTION INVESTIGATION */

export function Transactions(){
  const {data,error,busy}=useLoad<any[]>('/api/v1/domain/transactions');
  const [id,setId]=useState('');
  const [record,setRecord]=useState<any>(null);
  const [investigating,setInvestigating]=useState(false);
  const [investigationError,setInvestigationError]=useState('');

  async function investigate(){
    if(!id.trim())return;

    setInvestigating(true);
    setInvestigationError('');
    setRecord(null);

    try{
      const result=await api<any>(
        `/api/v1/domain/transactions/${encodeURIComponent(id.trim())}`
      );
      setRecord(result);
    }catch(e:any){
      setInvestigationError(e.message);
    }finally{
      setInvestigating(false);
    }
  }

  const order=record?.order||record;
  const reviews=record?.reviews||[];
  const amount=order?.amount;
  const currency=order?.currency||'INR';

  return <>
    <Heading
      title="Transaction intelligence"
      sub="Investigate orders, payment states, customer feedback and associated operational signals."
    />

    <div className="toolbar">
      <div className="search">
        <Search size={16}/>
        <input
          placeholder="Enter merchant order ID, e.g. ORD-009"
          value={id}
          onChange={e=>setId(e.target.value)}
          onKeyDown={e=>e.key==='Enter'&&investigate()}
        />
      </div>

      <button className="primary" onClick={investigate} disabled={investigating||!id.trim()}>
        {investigating?'Investigating…':'Investigate order'}
      </button>
    </div>

    {investigationError&&<div className="error">{investigationError}</div>}

    {record&&<>
      <Panel title="Order overview">
        <div className="metric-grid">
          <Metric label="Order value" value={amount!=null?money(amount):'—'} caption={currency} icon={Wallet}/>
          <Metric label="Payment status" value={order?.payment_status||'Unknown'} caption="Recorded payment state" icon={CheckCircle2}/>
          <Metric label="Customer" value={order?.customer_name||'—'} caption={order?.customer_id||'Customer reference'} icon={Users}/>
          <Metric label="Feedback records" value={reviews.length} caption="Associated reviews" icon={Activity}/>
        </div>

        <div className="form-grid">
          <div><small className="muted">Order ID</small><h3>{order?.id||id}</h3></div>
          <div><small className="muted">Product</small><h3>{order?.product||'—'}</h3></div>
          <div><small className="muted">Production batch</small><h3>{order?.batch||'—'}</h3></div>
          <div><small className="muted">Created</small><h3>{order?.created_at?new Date(order.created_at).toLocaleString():'—'}</h3></div>
        </div>
      </Panel>

      <Panel title="Payment verification">
        <div className="form-grid">
          <div><small className="muted">Payment state</small><h3>{order?.payment_status||'Not available'}</h3></div>
          <div><small className="muted">PayPal order reference</small><h3>{order?.paypal_order_id||'—'}</h3></div>
          <div><small className="muted">Capture reference</small><h3>{order?.capture_id||'—'}</h3></div>
          <div><small className="muted">Amount</small><h3>{amount!=null?money(amount):'—'} {currency}</h3></div>
        </div>

        <div className="notice warning">
          Payment status shown here is the status returned by the MerchantOS record. Verify against the payment provider before treating it as independently confirmed.
        </div>
      </Panel>

      <Panel title="Customer feedback">
        {reviews.length?reviews.map((review:any,index:number)=>(
          <article className="insight" key={review.id||index}>
            <span className="insight-icon"><AlertCircle size={17}/></span>
            <div>
              <b>{review.category||review.cluster_id||'Customer review'}</b>
              <p>{review.text||'No review text available.'}</p>
              <small className="muted">
                Rating: {review.rating??'—'} / 5
                {' · '}Severity: {review.severity||'—'}
                {' · '}Sentiment: {review.sentiment||'—'}
              </small>
            </div>
          </article>
        )):<p className="muted">No associated reviews were returned for this order.</p>}
      </Panel>
    </>}

    <Panel title="Recent transactions" extra={<span className="muted">{data?.length??0} records</span>}>
      {error&&<p className="error">{error}</p>}
      {busy&&<p className="muted">Loading transactions…</p>}

      <Table
        columns={['id','customer_name','product','amount','currency','payment_status']}
        rows={(data||[]).map(x=>({
          ...x,
          id:<button className="table-link" onClick={()=>{
            setId(x.id);
            setRecord(null);
            setTimeout(()=>api(`/api/v1/domain/transactions/${encodeURIComponent(x.id)}`).then(setRecord).catch(e=>setInvestigationError(e.message)),0);
            window.scrollTo({top:0,behavior:'smooth'});
          }}>{x.id}</button>,
          amount:x.amount!=null?money(x.amount):'—'
        }))}
      />
    </Panel>
  </>;
}

/* REFUNDS */

export function Refunds(){
  const {data,error,refresh}=useLoad<any[]>('/api/v1/domain/refunds');
  const [detail,setDetail]=useState<any>(null);

  const rows=(data||[]).map(x=>({
    ...x,
    id:<button className="table-link" onClick={async()=>{
      try{
        setDetail(await api(`/api/v1/domain/refunds/${encodeURIComponent(x.id)}`));
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

/* DISPUTE INVESTIGATION */

export function Disputes(){
  const {data,error,refresh}=useLoad<any[]>('/api/paypal/disputes');
  const {data:local}=useLoad<any[]>('/api/v1/domain/disputes');

  const [detail,setDetail]=useState<any>(null);
  const [loading,setLoading]=useState(false);
  const [detailError,setDetailError]=useState('');

  async function investigate(id:string,isPayPal:boolean){
    setLoading(true);
    setDetail(null);
    setDetailError('');

    try{
      const path=isPayPal
        ?`/api/paypal/disputes/${encodeURIComponent(id)}`
        :`/api/v1/domain/disputes/${encodeURIComponent(id)}`;

      setDetail(await api<any>(path));
    }catch(e:any){
      setDetailError(e.message);
    }finally{
      setLoading(false);
    }
  }

  async function syncPayPal(){
    try{
      await api('/api/paypal/disputes/sync',{method:'POST'});
      refresh();
    }catch(e:any){
      setDetailError(e.message);
    }
  }

  const missing=detail?.missing_types||[];
  const covered=detail?.covered_types||[];
  const required=detail?.required_evidence_types||[];
  const present=detail?.present_evidence||[];

  const coverage=Number(detail?.coverage_pct??0);
  const assessment=String(detail?.assessment||detail?.status||'Assessment pending');

  return <>
    <Heading
      title="Dispute center"
      sub="Investigate dispute records, identify evidence gaps and prepare for human-reviewed responses."
      action={<button className="secondary" onClick={syncPayPal}><RefreshCw size={15}/> Sync PayPal</button>}
    />

    {error&&<div className="error">{error}</div>}
    {detailError&&<div className="error">{detailError}</div>}

    <div className="two-col">
      <Panel title="PayPal disputes">
        <Table
          columns={['dispute_id','status','reason','lifecycle_stage']}
          rows={(data||[]).map(x=>({
            ...x,
            dispute_id:<button className="table-link" onClick={()=>investigate(x.dispute_id,true)}>{x.dispute_id}</button>
          }))}
        />
        <p className="muted">Provider-synchronized records. Their current state must be confirmed with PayPal.</p>
      </Panel>

      <Panel title="Local illustrative disputes">
        <Table
          columns={['id','order_id','reason','status']}
          rows={(local||[]).map(x=>({
            ...x,
            id:<button className="table-link" onClick={()=>investigate(x.id,false)}>{x.id}</button>
          }))}
        />
        <p className="muted">Local demo records are not represented as real PayPal disputes.</p>
      </Panel>
    </div>

    {loading&&<Panel title="Dispute investigation"><p className="muted">Loading investigation…</p></Panel>}

    {detail&&<>
      <Panel title="Dispute overview">
        <div className="form-grid">
          <div><small className="muted">Dispute reference</small><h3>{detail.dispute_id||'Local dispute'}</h3></div>
          <div><small className="muted">Related order</small><h3>{detail.order_id||'—'}</h3></div>
          <div><small className="muted">Reason</small><h3>{String(detail.reason||'—').replace(/_/g,' ')}</h3></div>
          <div><small className="muted">Assessment</small><h3>{assessment.replace(/_/g,' ')}</h3></div>
        </div>
      </Panel>

      <Panel title="Evidence coverage">
        <div className="metric-grid">
          <Metric label="Coverage" value={`${coverage}%`} caption="Required evidence coverage" icon={ShieldCheck}/>
          <Metric label="Required" value={required.length} caption="Evidence categories" icon={FileText}/>
          <Metric label="Available" value={present.length+covered.length} caption="Evidence entries reported" icon={CheckCircle2}/>
          <Metric label="Missing" value={missing.length} caption="Outstanding evidence categories" icon={AlertCircle}/>
        </div>

        <div style={{height:10,background:'#e7eadf',borderRadius:6,overflow:'hidden'}}>
          <div style={{height:'100%',width:`${Math.max(0,Math.min(100,coverage))}%`,background:'#819b48',transition:'width .3s'}}/>
        </div>

        <p className="muted">{coverage}% reported coverage. This measures evidence categories, not the probability of winning a dispute.</p>
      </Panel>

      <Panel title="Evidence checklist">
        {required.length?required.map((item:string,index:number)=>{
          const isCovered=covered.includes(item)||present.includes(item);

          return <article className="insight" key={item}>
            <span className="insight-icon">
              {isCovered?<CheckCircle2 size={17}/>:<AlertCircle size={17}/>}
            </span>
            <div>
              <b>{item.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</b>
              <p>{isCovered?'Evidence category reported as available.':'Evidence category reported as missing.'}</p>
            </div>
            <strong>{isCovered?'Available':'Missing'}</strong>
          </article>;
        }):<p className="muted">No required evidence checklist was returned by the API.</p>}
      </Panel>

      {detail.payment_record&&
        <Panel title="Associated payment record">
          <div className="form-grid">
            <div><small className="muted">Payment reference</small><h3>{detail.payment_record.id||'—'}</h3></div>
            <div><small className="muted">Payment state</small><h3>{detail.payment_record.payment_status||'—'}</h3></div>
            <div><small className="muted">Amount</small><h3>{detail.payment_record.amount??'—'} {detail.payment_record.currency||''}</h3></div>
            <div><small className="muted">Capture reference</small><h3>{detail.payment_record.capture_id||'—'}</h3></div>
          </div>
        </Panel>
      }

      <Panel title="Recommended investigation steps">
        {missing.length?
          <div className="notice warning">
            <b>Evidence gaps identified.</b>
            <p>Collect and verify the missing evidence categories before preparing a response:</p>
            <ul>{missing.map((item:string)=><li key={item}>{item.replace(/_/g,' ')}</li>)}</ul>
          </div>
          :
          <div className="notice">
            No missing evidence categories were reported. Review evidence quality and accuracy before proceeding.
          </div>
        }

        <p className="muted">
          Merchant review and authorization are required. MerchantOS does not automatically submit a dispute response.
        </p>
      </Panel>

      {detail.limitations&&
        <Panel title="Assessment limitations">
          <p>{detail.limitations}</p>
        </Panel>
      }
    </>}
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
  const {data,error,refresh}=useLoad<any[]>('/api/v1/domain/evidence');
  const [file,setFile]=useState<File|null>(null);
  const [order,setOrder]=useState('');
  const [type,setType]=useState('DELIVERY_CONFIRMATION');
  const [description,setDescription]=useState('');

  async function upload(){
    if(!file||!order)return;
    const f=new FormData();
    f.append('file',file);

    try{
      await api(`/api/v1/domain/evidence/upload?order_id=${encodeURIComponent(order)}&evidence_type=${encodeURIComponent(type)}&description=${encodeURIComponent(description)}`,{
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
      <Table columns={['id','order_id','evidence_type','description','integrity_status','created_at']} rows={data||[]}/>
      {error&&<p className="error">{error}</p>}
      <button className="secondary" onClick={refresh}>Refresh</button>
    </Panel>
  </>;
}

/* AUDIT */

export function Audit() {
  const {data,error,busy} = useLoad<any[]>('/api/v1/domain/audit');

  function parseDetail(value:any) {
    if (typeof value !== 'string') return value || {};

    try {
      return JSON.parse(value);
    } catch {
      return {description:value};
    }
  }

  function format(value:any) {
    return String(value ?? 'Not recorded')
      .replace(/_/g,' ')
      .replace(/\b\w/g,c=>c.toUpperCase());
  }

  function formatDate(value:any) {
    if (!value) return 'Timestamp unavailable';

    const date = new Date(value);

    return Number.isNaN(date.getTime())
      ? 'Invalid timestamp'
      : date.toLocaleString();
  }

  return (
    <>
      <Heading
        title="Trust & audit"
        sub="A chronological record of consequential operational and financial events."
      />

      {error && <div className="error">{error}</div>}

      <Panel
        title="Audit history"
        extra={
          <span className="muted">
            {(data || []).length} recorded events
          </span>
        }
      >

        {busy ? (
          <p className="muted">Loading audit history…</p>
        ) : !data?.length ? (
          <div className="empty-state">
            <b>No audit events recorded</b>
            <p>Operational events will appear here.</p>
          </div>
        ) : (

          <div className="audit-timeline">

            {data.map((item:any,index:number) => {

              const detail = parseDetail(item.detail);

              const event =
                item.event ||
                item.action ||
                item.event_type ||
                item.type ||
                'Operational event';

              const actor =
                item.actor ||
                item.actor_email ||
                item.user_id ||
                'System';

              const entity =
                item.entity ||
                item.entity_type ||
                item.resource ||
                'General';

              const entries =
                typeof detail === 'object' && detail !== null
                  ? Object.entries(detail).filter(
                      ([key]) =>
                        !/(password|token|secret|authorization|api_key)/i.test(key)
                    )
                  : [];

              return (
                <article
                  className="audit-entry"
                  key={item.id || index}
                >

                  <div className="audit-marker">
                    <span><ShieldCheck size={16}/></span>
                  </div>

                  <div className="audit-body">

                    <div className="audit-header">

                      <div>
                        <h4>{format(event)}</h4>

                        <small>
                          {formatDate(item.created_at)}
                        </small>
                      </div>

                      <span className="audit-index">
                        #{index + 1}
                      </span>

                    </div>

                    <div className="audit-meta">

                      <span>
                        Actor: <b>{format(actor)}</b>
                      </span>

                      <span>
                        Entity: <b>{format(entity)}</b>
                      </span>

                    </div>

                    {entries.length > 0 && (

                      <div className="audit-details">

                        {entries.map(([key,value]:any) => (

                          <div
                            className="audit-detail-item"
                            key={key}
                          >
                            <small>{format(key)}</small>

                            <b>
                              {typeof value === 'object'
                                ? JSON.stringify(value)
                                : String(value ?? '—')}
                            </b>
                          </div>

                        ))}

                      </div>

                    )}

                    {typeof detail === 'string' && (
                      <p className="audit-description">
                        {detail}
                      </p>
                    )}

                  </div>

                </article>
              );
            })}

          </div>

        )}

      </Panel>
    </>
  );
        }
