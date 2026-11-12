import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import {Activity,AlertCircle,CheckCircle2,Clock3,RefreshCw,Wallet} from 'lucide-react';

type Row=Record<string,any>;
const label=(v:any)=>String(v??'—').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const date=(v:any)=>{if(!v)return '—';const d=new Date(v);return Number.isNaN(d.getTime())?'—':d.toLocaleString();};
const detail=(v:any)=>{if(v&&typeof v==='object')return v;if(typeof v==='string'){try{return JSON.parse(v)}catch{return {description:v}}}return {};};

export default function ExecutionTimeline(){
 const [approvals,setApprovals]=useState<Row[]>([]);
 const [events,setEvents]=useState<Row[]>([]);
 const [busy,setBusy]=useState(true);
 const [acting,setActing]=useState('');
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [capture,setCapture]=useState('');
 const [amount,setAmount]=useState('');
 const [currency,setCurrency]=useState('USD');
 const [reason,setReason]=useState('');
 const [expanded,setExpanded]=useState<string|null>(null);

 async function load(){
  setBusy(true);setError('');
  try{
   const [a,e]=await Promise.all([
    api<Row[]>('/api/v1/operations/financial/refund-approvals'),
    api<Row[]>('/api/v1/domain/audit')
   ]);
   setApprovals(Array.isArray(a)?a:[]);
   setEvents(Array.isArray(e)?e:[]);
  }catch(err:any){setError(err.message||'Could not load action records.');}
  finally{setBusy(false);}
 }
 useEffect(()=>{void load();const timer=window.setInterval(()=>void load(),20000);return()=>window.clearInterval(timer);},[]);

 async function perform(id:string,action:'reconcile'|'approve'|'reject'|'execute'){
  let note='';
  if(action==='approve'||action==='reject'){
   note=window.prompt(action==='approve'?'Add an approval note (at least 5 characters):':'Why are you rejecting this refund? (at least 5 characters):')||'';
   if(note.trim().length<5){setError('A decision note of at least 5 characters is required.');return;}
  }
  setActing(id+action);setError('');setNotice('');
  try{
   let result:any;
   const base='/api/v1/operations/financial/refund-approvals/'+encodeURIComponent(id);
   if(action==='reconcile') result=await api(base+'/reconcile',{method:'POST'});
   if(action==='approve'||action==='reject') result=await api(base+'/decision',{method:'POST',body:JSON.stringify({decision:action.toUpperCase(),note:note.trim()})});
   if(action==='execute') result=await api(base+'/execute',{method:'POST'});
   setNotice(result?.note||('Refund request updated: '+(result?.status||'action recorded')+'.'));
   await load();
  }catch(err:any){setError(err.message||'The action could not be completed.');}
  finally{setActing('');}
 }

 async function createRequest(e:any){
  e.preventDefault();setActing('create');setError('');setNotice('');
  try{
   const result:any=await api('/api/v1/operations/financial/refund-approvals',{method:'POST',body:JSON.stringify({
    capture_id:capture.trim(),amount,currency,reason:reason.trim(),request_key:crypto.randomUUID()
   })});
   setNotice(result?.note||'Refund request created and queued for PayPal reconciliation.');
   setCapture('');setAmount('');setReason('');
   await load();
  }catch(err:any){setError(err.message||'Could not create the refund request.');}
  finally{setActing('');}
 }

 return <section className="page action-center">
 <style>{`
 .action-center{display:grid;gap:16px;min-width:0}.action-center .page-heading{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
 .action-panel{background:var(--panel,#fff);border:1px solid var(--border,#e5e1d8);border-radius:15px;padding:16px;min-width:0}
 .action-panel-head{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.action-panel h3{margin:0}
 .action-caption{font-size:12px;color:#778177;line-height:1.5;margin:5px 0 0}.action-count{font-size:10px;font-weight:800;letter-spacing:.08em;padding:6px 9px;border-radius:99px;background:#eef1e9;color:#50634e}
 .refund-list{display:grid;gap:10px;margin-top:14px}.refund-item{border:1px solid #e6e8e1;border-radius:12px;padding:13px;display:grid;gap:10px}
 .refund-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}.refund-amount{font-size:19px;font-weight:750;color:#29372e}.refund-ref{font-size:11px;color:#7c867d;overflow-wrap:anywhere;margin-top:4px}
 .refund-status{font-size:10px;font-weight:800;letter-spacing:.06em;padding:6px 9px;border-radius:99px;background:#f1f0e9;color:#596653}
 .refund-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.refund-facts div{background:#f7f7f2;border-radius:8px;padding:9px;min-width:0}.refund-facts small{display:block;font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:#7c867d}.refund-facts b{display:block;font-size:12px;margin-top:4px;overflow-wrap:anywhere}
 .refund-buttons{display:flex;gap:8px;flex-wrap:wrap}.refund-buttons button,.action-panel button{cursor:pointer}.action-btn{border:1px solid #d8ded4;border-radius:9px;background:white;color:#344338;padding:9px 12px;font-weight:700;font-size:12px}.action-btn.primary{background:#293f33;color:white;border-color:#293f33}.action-btn.reject{color:#a13e36;border-color:#e6c9c4}.action-btn:disabled{opacity:.5;cursor:wait}
 .action-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin-top:14px}.action-form label{display:grid;gap:6px;font-size:12px;font-weight:700}.action-form input,.action-form select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #d9ddd5;border-radius:9px;background:white;color:inherit}.action-form .wide{grid-column:1/-1}
 .audit-list{display:grid;gap:9px;margin-top:13px}.audit-item{border:1px solid #e8e9e3;border-radius:11px;padding:12px;display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px}.audit-icon{width:28px;height:28px;display:grid;place-items:center;border-radius:8px;background:#eff2ec;color:#60715e}.audit-title{font-size:12px;font-weight:800}.audit-sub{font-size:10px;color:#818b82;margin-top:4px;overflow-wrap:anywhere}.audit-details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.audit-details div{padding:8px;background:#f7f7f2;border-radius:8px;min-width:0}.audit-details dt{font-size:9px;text-transform:uppercase;color:#788278}.audit-details dd{margin:4px 0 0;font-size:11px;overflow-wrap:anywhere;word-break:break-word}
 @media(max-width:600px){.action-panel{padding:13px}.refund-facts,.action-form,.audit-details{grid-template-columns:1fr}.action-form .wide{grid-column:auto}}
 `}</style>
 <div className="page-heading"><div><div className="action-caption">STORE WORKFLOW / HUMAN CONTROL</div><h1>Actions</h1><p>Refund decisions first. Payment execution and the audit trail follow below.</p></div><button className="secondary" onClick={()=>void load()} disabled={busy}><RefreshCw size={15}/> Refresh</button></div>
 {error&&<div className="error" role="alert">{error}</div>}{notice&&<div className="notice" role="status">{notice}</div>}

 <section className="action-panel">
  <div className="action-panel-head"><div><h3>Refund decisions</h3><p className="action-caption">Review the request, verify it with PayPal, then approve or reject. The requester cannot approve their own request.</p></div><span className="action-count">{approvals.length} REQUESTS</span></div>
  {busy?<p className="action-caption">Loading requests…</p>:!approvals.length?<p className="action-caption">No refund requests are waiting. New requests can be created below.</p>:
  <div className="refund-list">{approvals.map(a=>{
   const status=String(a.status||'UNKNOWN').toUpperCase(),id=String(a.id);
   const pending=status==='PENDING_RECONCILIATION',ready=status==='PENDING_APPROVAL',approved=status==='APPROVED';
   return <article className="refund-item" key={id}>
    <div className="refund-top"><div><div className="refund-amount">{a.amount} {a.currency||''}</div><div className="refund-ref">Capture: {a.capture_id||'Not recorded'} · Request: {id.slice(0,12)}</div></div><span className="refund-status">{label(status)}</span></div>
    <div className="refund-facts"><div><small>Reason</small><b>{a.reason||'Not recorded'}</b></div><div><small>Requested by</small><b>{a.requester_id||'Unknown'}</b></div><div><small>Created</small><b>{date(a.created_at)}</b></div><div><small>Independent approver</small><b>{a.approver_id||'Awaiting decision'}</b></div></div>
    <div className="refund-buttons">
     {pending&&<button className="action-btn primary" disabled={!!acting} onClick={()=>void perform(id,'reconcile')}>{acting===id+'reconcile'?'Checking PayPal…':'Reconcile with PayPal'}</button>}
     {ready&&<><button className="action-btn primary" disabled={!!acting} onClick={()=>void perform(id,'approve')}>{acting===id+'approve'?'Saving…':'Approve refund'}</button><button className="action-btn reject" disabled={!!acting} onClick={()=>void perform(id,'reject')}>{acting===id+'reject'?'Saving…':'Reject refund'}</button></>}
     {approved&&<button className="action-btn primary" disabled={!!acting} onClick={()=>void perform(id,'execute')}>Execute Sandbox refund</button>}
     {status==='REJECTED'&&<span className="action-caption">Rejected. No payment was sent.</span>}
     {status==='COMPLETED'&&<span className="action-caption">Provider execution completed. Check the PayPal refund reference below.</span>}
     {status==='BLOCKED'&&<span className="action-caption">Blocked by provider or policy checks. Review the reason before taking further action.</span>}
    </div>
   </article>;
  })}</div>}
 </section>

 <section className="action-panel">
  <div className="action-panel-head"><div><h3>Submit a refund request</h3><p className="action-caption">A new request always starts with server-side PayPal reconciliation.</p></div><Wallet size={18}/></div>
  <form className="action-form" onSubmit={createRequest}>
   <label className="wide">PayPal capture ID<input required value={capture} onChange={e=>setCapture(e.target.value)} placeholder="Completed PayPal Sandbox capture ID"/></label>
   <label>Amount<input required type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} placeholder="25.00"/></label>
   <label>Currency<select value={currency} onChange={e=>setCurrency(e.target.value)}>{['USD','INR','EUR','GBP'].map(c=><option key={c}>{c}</option>)}</select></label>
   <label className="wide">Reason<input required minLength={10} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain why this refund is requested"/></label>
   <div className="wide"><button className="action-btn primary" disabled={!!acting}>{acting==='create'?'Submitting…':'Create refund request'}</button></div>
  </form>
 </section>

 <section className="action-panel">
  <div className="action-panel-head"><div><h3>Execution history</h3><p className="action-caption">A readable record of operational events. Open an event to inspect its details.</p></div><span className="action-count">{events.length} EVENTS</span></div>
  {busy?<p className="action-caption">Loading history…</p>:!events.length?<p className="action-caption">No audit events recorded yet.</p>:
  <div className="audit-list">{events.map((e,i)=>{
   const name=String(e.event||e.action||e.event_type||'OPERATIONAL_EVENT'),id=String(e.id||i),expandedNow=expanded===id;
   const values=Object.entries(detail(e.detail)).filter(([k])=>!/(secret|token|password|authorization|api.?key)/i.test(k));
   const completed=/COMPLETED|SUCCEEDED|CAPTURED|APPROVED/.test(name),failed=/FAILED|REJECTED|ERROR/.test(name);
   return <article className="audit-item" key={id}><div className="audit-icon">{failed?<AlertCircle size={15}/>:completed?<CheckCircle2 size={15}/>:<Activity size={15}/>}</div><div><div className="refund-top"><span className="audit-title">{label(name)}</span><time className="audit-sub">{date(e.created_at||e.timestamp)}</time></div><div className="audit-sub">{label(e.entity_type||e.entity||'System')} {e.entity_id||''} · {e.actor||e.actor_email||'System'}</div>{values.length>0&&<button className="action-btn" style={{marginTop:9}} onClick={()=>setExpanded(expandedNow?null:id)}>{expandedNow?'Hide details':'View details'}</button>}{expandedNow&&<dl className="audit-details">{values.map(([k,v])=><div key={k}><dt>{label(k)}</dt><dd>{typeof v==='object'?JSON.stringify(v):String(v??'—')}</dd></div>)}</dl>}</div></article>;
  })}</div>}
 </section>
 <p className="action-caption">Refund actions use PayPal Sandbox. Approval is separate from execution; provider confirmation is required before a refund is treated as completed.</p>
 </section>;
}
