import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Activity, AlertCircle, CheckCircle2, Clock3, RefreshCw, ShieldCheck, Wallet } from 'lucide-react';

type AnyRow = Record<string, any>;

const money=(value:any)=>Number(value||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
const label=(value:any)=>String(value??'—').replaceAll('_',' ').replace(/\\b\\w/g,c=>c.toUpperCase());
const date=(value:any)=>{if(!value)return 'Time unavailable';const d=new Date(value);return Number.isNaN(d.getTime())?'Time unavailable':d.toLocaleString();};
const safeDetail=(value:any)=>{if(typeof value!=='string')return value&&typeof value==='object'?value:{};try{return JSON.parse(value)}catch{return {description:value}}};

export default function ExecutionTimeline(){
  const [rows,setRows]=useState<AnyRow[]>([]);
  const [approvals,setApprovals]=useState<AnyRow[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(true);
  const [acting,setActing]=useState('');
  const [expanded,setExpanded]=useState<string|null>(null);
  const [capture,setCapture]=useState('');
  const [amount,setAmount]=useState('');
  const [currency,setCurrency]=useState('USD');
  const [reason,setReason]=useState('');
  const [notice,setNotice]=useState('');

  const load=async()=>{
    setBusy(true);setError('');
    try{
      const [events,requests]=await Promise.all([
        api<AnyRow[]>('/api/v1/domain/audit'),
        api<AnyRow[]>('/api/v1/operations/financial/refund-approvals')
      ]);
      setRows(Array.isArray(events)?events:[]);
      setApprovals(Array.isArray(requests)?requests:[]);
    }catch(e:any){setError(e.message||'Could not load action records.');}
    finally{setBusy(false);}
  };
  useEffect(()=>{void load();const timer=window.setInterval(()=>void load(),20000);return()=>window.clearInterval(timer);},[]);

  async function act(id:string,action:'reconcile'|'approve'|'reject'|'execute'){
    setActing(id+action);setError('');setNotice('');
    try{
      let result:any;
      if(action==='reconcile') result=await api('/api/v1/operations/financial/refund-approvals/'+encodeURIComponent(id)+'/reconcile',{method:'POST'});
      if(action==='approve'||action==='reject'){
        const note=window.prompt(action==='approve'?'Approval note (required by your review process):':'Reason for rejection:');
        if(note===null)return;
        result=await api('/api/v1/operations/financial/refund-approvals/'+encodeURIComponent(id)+'/decision',{method:'POST',body:JSON.stringify({decision:action.toUpperCase(),note})});
      }
      if(action==='execute') result=await api('/api/v1/operations/financial/refund-approvals/'+encodeURIComponent(id)+'/execute',{method:'POST',body:JSON.stringify({})});
      setNotice(result?.note||result?.status||'Action recorded. Refreshing provider and audit state.');
      await load();
    }catch(e:any){setError(e.message||'Action could not be completed.');}
    finally{setActing('');}
  }

  async function createRequest(e:any){
    e.preventDefault();setActing('create');setError('');setNotice('');
    try{
      const result:any=await api('/api/v1/operations/financial/refund-approvals',{method:'POST',body:JSON.stringify({
        capture_id:capture.trim(),amount,currency,reason:reason.trim(),request_key:crypto.randomUUID()
      })});
      setNotice(result?.note||'Refund request created. Reconcile it with PayPal before approval.');
      setCapture('');setAmount('');setReason('');
      await load();
    }catch(e:any){setError(e.message||'Refund request could not be created.');}
    finally{setActing('');}
  }

  return <section className="page action-center">
    <style>{`
      .action-center{display:grid;gap:18px;min-width:0}
      .action-center .page-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
      .action-card{background:var(--panel,#fff);border:1px solid var(--border,#e5e1d8);border-radius:16px;padding:16px;min-width:0;box-shadow:0 5px 20px #17203308}
      .action-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
      .action-kicker{font-size:10px;letter-spacing:.14em;font-weight:800;color:#758071}
      .action-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}
      .action-form label{display:grid;gap:6px;font-size:12px;font-weight:700;color:var(--text,#26332c);min-width:0}
      .action-form input,.action-form select{width:100%;box-sizing:border-box;border:1px solid var(--border,#d9ddd5);border-radius:10px;padding:12px;background:var(--surface,#fff);color:inherit;font:inherit}
      .action-form .wide{grid-column:1/-1}
      .action-btn{border:1px solid #d8ded4;border-radius:9px;background:#fff;color:#26372d;padding:9px 12px;font-weight:700;font-size:12px;cursor:pointer}
      .action-btn.primary{background:#263d31;color:white;border-color:#263d31}
      .action-btn.danger{color:#a33a32;border-color:#e8c7c2}
      .action-btn:disabled{opacity:.45;cursor:wait}
      .action-list{display:grid;gap:10px;margin-top:12px}
      .approval-item{border:1px solid #e7e9e2;border-radius:13px;padding:14px;display:grid;gap:10px}
      .approval-top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
      .approval-status{border-radius:99px;padding:5px 9px;background:#edf2e9;color:#455b43;font-size:10px;font-weight:800;letter-spacing:.06em}
      .approval-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .approval-meta small{display:block;color:#788278;font-size:10px;text-transform:uppercase;letter-spacing:.08em}
      .approval-meta b{display:block;margin-top:3px;overflow-wrap:anywhere;font-size:13px}
      .approval-actions{display:flex;gap:8px;flex-wrap:wrap}
      .timeline{display:grid;gap:10px;margin-top:12px}
      .event-card{border:1px solid #e9e9e3;border-radius:13px;padding:13px;display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px}
      .event-icon{width:28px;height:28px;border-radius:9px;background:#eef1eb;display:grid;place-items:center;color:#536a58}
      .event-title{font-size:13px;font-weight:800;color:#29362e}
      .event-sub{font-size:11px;color:#879087;margin-top:4px;overflow-wrap:anywhere}
      .event-details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}
      .event-details div{background:#f7f7f2;border-radius:8px;padding:8px;min-width:0}
      .event-details dt{font-size:10px;color:#7a857b;text-transform:uppercase;letter-spacing:.06em}
      .event-details dd{margin:4px 0 0;font-size:12px;color:#354139;overflow-wrap:anywhere;word-break:break-word}
      .action-muted{font-size:12px;color:#788278}
      @media(max-width:600px){.action-form,.approval-meta,.event-details{grid-template-columns:1fr}.action-form .wide{grid-column:auto}.action-card{padding:13px}}
    `}</style>
    <div className="page-heading"><div><div className="action-kicker">MERCHANT WORKSPACE / HUMAN CONTROL</div><h1>Actions</h1><p>Review refund requests, reconcile payment facts, record decisions and verify outcomes.</p></div><button className="secondary" onClick={()=>void load()} disabled={busy}><RefreshCw size={15}/> Refresh</button></div>
    {error&&<div className="error" role="alert">{error}</div>}
    {notice&&<div className="notice" role="status">{notice}</div>}

    <section className="action-card">
      <div className="action-head"><div><h3><Wallet size={17}/> Create refund request</h3><p className="action-muted">Use a real PayPal Sandbox capture ID. Demo placeholder captures cannot be refunded.</p></div><span className="approval-status">SANDBOX ONLY</span></div>
      <form className="action-form" onSubmit={createRequest}>
        <label className="wide">PayPal capture ID<input value={capture} onChange={e=>setCapture(e.target.value)} required placeholder="Paste the completed capture ID"/></label>
        <label>Refund amount<input type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} required placeholder="0.00"/></label>
        <label>Currency<select value={currency} onChange={e=>setCurrency(e.target.value)}>{['USD','INR','EUR','GBP'].map(x=><option key={x}>{x}</option>)}</select></label>
        <label className="wide">Reason (10–1000 characters)<input value={reason} onChange={e=>setReason(e.target.value)} minLength={10} maxLength={1000} required placeholder="Explain why this refund is being requested"/></label>
        <div className="wide"><button className="action-btn primary" disabled={acting==='create'}>{acting==='create'?'Creating request…':'Create refund request'}</button></div>
      </form>
    </section>

    <section className="action-card">
      <div className="action-head"><div><h3>Refund approval queue</h3><p className="action-muted">Separate maker-checker approval. Reconciliation must succeed before a decision is available.</p></div><span className="approval-status">{approvals.length} REQUESTS</span></div>
      {busy?<p className="action-muted">Loading refund requests…</p>:!approvals.length?<div className="empty-state"><b>No refund requests yet</b><p>Create a request above or review the refund investigations page.</p></div>:
      <div className="action-list">{approvals.map(item=>{
        const status=String(item.status||'UNKNOWN').toUpperCase();
        const pending=status==='PENDING_RECONCILIATION';
        const ready=status==='PENDING_APPROVAL';
        const approved=status==='APPROVED';
        const id=String(item.id);
        return <article className="approval-item" key={id}>
          <div className="approval-top"><div><b>{money(item.amount)} {item.currency||''}</b><div className="event-sub">Request {id.slice(0,12)} · Capture {item.capture_id||'not recorded'}</div></div><span className="approval-status">{label(status)}</span></div>
          <div className="approval-meta"><div><small>Requested by</small><b>{item.requester_id||'Unknown'}</b></div><div><small>Created</small><b>{date(item.created_at)}</b></div><div><small>Reason</small><b>{item.reason||'Not recorded'}</b></div><div><small>Approver</small><b>{item.approver_id||'Awaiting independent reviewer'}</b></div></div>
          <div className="approval-actions">
            {pending&&<button className="action-btn primary" disabled={!!acting} onClick={()=>void act(id,'reconcile')}>Reconcile with PayPal</button>}
            {ready&&<><button className="action-btn primary" disabled={!!acting} onClick={()=>void act(id,'approve')}>Approve request</button><button className="action-btn danger" disabled={!!acting} onClick={()=>void act(id,'reject')}>Reject request</button></>}
            {approved&&<button className="action-btn primary" disabled={!!acting} onClick={()=>void act(id,'execute')}>Execute Sandbox refund</button>}
            {status==='REJECTED'&&<span className="action-muted">Request rejected. No refund was executed.</span>}
            {status==='COMPLETED'&&<span className="action-muted">Provider execution completed. Verify the returned PayPal refund reference.</span>}
          </div>
          <small className="action-muted">Execution is controlled by backend policy and PAYPAL_EXECUTION_ENABLED. Approval does not itself move money.</small>
        </article>;
      })}</div>}
    </section>

    <section className="action-card">
      <div className="action-head"><div><h3><Activity size={17}/> Operational event stream</h3><p className="action-muted">Compact, read-only audit history. Sensitive fields are hidden.</p></div><span className="approval-status">{rows.length} EVENTS</span></div>
      {busy?<p className="action-muted">Loading events…</p>:!rows.length?<div className="empty-state"><b>No audit events recorded</b><p>Consequential operations will appear here.</p></div>:
      <div className="timeline">{rows.map((row,index)=>{
        const event=String(row.event||row.action||row.event_type||'OPERATIONAL_EVENT');
        const detail=safeDetail(row.detail);
        const entries=Object.entries(detail).filter(([key])=>!/(secret|token|password|authorization|api.?key)/i.test(key));
        const id=String(row.id||index);
        const open=expanded===id;
        const completed=/COMPLETED|SUCCEEDED|CAPTURED|APPROVED/.test(event);
        const failed=/FAILED|REJECTED|ERROR/.test(event);
        const summary=entries.slice(0,2).map(([k,v])=>label(k)+': '+(typeof v==='object'?JSON.stringify(v):String(v??'—'))).join(' · ');
        return <article className="event-card" key={id}><div className="event-icon">{failed?<AlertCircle size={16}/>:completed?<CheckCircle2 size={16}/>:<Clock3 size={16}/>}</div><div><div className="approval-top"><span className="event-title">{label(event)}</span><time className="event-sub">{date(row.created_at||row.timestamp)}</time></div><div className="event-sub">{label(row.entity_type||row.entity||'system')} {row.entity_id||''} · {row.actor||row.actor_email||'System'}</div>{summary&&<p className="action-muted">{summary}</p>}{entries.length>2&&<button className="action-btn" onClick={()=>setExpanded(open?null:id)}>{open?'Hide details':'View details'}</button>}{open&&<dl className="event-details">{entries.map(([key,value])=><div key={key}><dt>{label(key)}</dt><dd>{typeof value==='object'?JSON.stringify(value):String(value??'—')}</dd></div>)}</dl>}</div></article>;
      })}</div>}
    </section>
    <p className="action-muted">Refund execution is PayPal Sandbox only. A rejected request is not refunded; an approved request still requires a separate execution step and provider confirmation.</p>
  </section>;
}
