import { useEffect, useState } from 'react';
import { api } from '../lib/api';

type AuditRow = { id: number | string; event: string; actor: string; entity: string; detail: string; created_at: string };

/** Lightweight native timeline: avoids a licensed/private scheduler dependency. */
export default function ExecutionTimeline(){
  const [rows,setRows]=useState<AuditRow[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(true);
  const load=()=>{
    setBusy(true);setError('');
    api<AuditRow[]>('/api/audit')
      .then(data=>setRows(Array.isArray(data)?data:[]))
      .catch((e:any)=>setError(e.message||'Could not load audit events'))
      .finally(()=>setBusy(false));
  };
  useEffect(()=>{load();const timer=window.setInterval(load,15000);return()=>window.clearInterval(timer);},[]);
  return <section className="page">
    <div className="page-heading"><div><h1>Execution timeline</h1><p>Chronological operational events from the persisted audit stream. Refreshes every 15 seconds.</p></div><button className="secondary" onClick={load} disabled={busy}>Refresh</button></div>
    {error&&<div className="error" role="alert">{error}</div>}
    {busy&&<p className="muted">Loading audit events…</p>}
    {!busy&&!rows.length&&!error&&<div className="panel"><p className="muted">No audit events have been recorded yet.</p></div>}
    <div className="panel execution-timeline-panel"><div className="panel-head"><h3>MerchantOS operational event stream</h3><span className="muted">{rows.length} audit events · read-only</span></div>
      <ol className="execution-timeline">{rows.map((row)=>{
        const failed=(row.event||'').includes('FAILED');
        const completed=(row.event||'').includes('COMPLETED');
        return <li key={String(row.id)} className={failed?'is-failed':completed?'is-completed':''}>
          <span className="execution-timeline-dot" aria-hidden="true"/>
          <div className="execution-timeline-content"><div className="execution-timeline-top"><b>{(row.event||'EVENT').replaceAll('_',' ')}</b><time dateTime={row.created_at}>{row.created_at?new Date(row.created_at).toLocaleString():'Time unavailable'}</time></div>
            <p>{row.entity||'system'} · {row.actor||'system'}</p>{row.detail&&<small>{row.detail}</small>}
          </div>
        </li>;
      })}</ol>
    </div>
    <p className="muted">This view displays persisted audit events, not model private reasoning. Event timestamps are shown as recorded by the source service.</p>
  </section>;
}
