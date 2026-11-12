import { useEffect, useState } from 'react';
import { api } from '../lib/api';

type AuditRow = { id: number | string; event?: string; action?: string; actor?: string; actor_email?: string; entity?: string; entity_type?: string; entity_id?: string; detail?: unknown; created_at?: string; timestamp?: string };

/** Lightweight native timeline: avoids a licensed/private scheduler dependency. */
export default function ExecutionTimeline(){
  const [rows,setRows]=useState<AuditRow[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(true);
  const load=()=>{
    setBusy(true);setError('');
    api<AuditRow[]>('/api/v1/domain/audit')
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
        const event = row.event || row.action || 'OPERATIONAL_EVENT';
        const failed=event.includes('FAILED');
        const completed=event.includes('COMPLETED') || event.includes('SUCCEEDED');
        let detail:any = row.detail ?? {};
        if(typeof detail === 'string'){try{detail=JSON.parse(detail)}catch{detail={description:detail}}}
        const safeEntries=detail && typeof detail==='object' && !Array.isArray(detail)
          ? Object.entries(detail).filter(([key])=>!/(secret|token|password|authorization|api.?key)/i.test(key))
          : [];
        return <li key={String(row.id)} className={failed?'is-failed':completed?'is-completed':''}>
          <span className="execution-timeline-dot" aria-hidden="true"/>
          <div className="execution-timeline-content"><div className="execution-timeline-top"><b>{event.replaceAll('_',' ')}</b><time dateTime={row.created_at}>{(row.created_at||row.timestamp)?new Date(String(row.created_at||row.timestamp)).toLocaleString():'Time unavailable'}</time></div>
            <p>{row.entity_type||row.entity||'system'} {row.entity_id||''} · {row.actor||row.actor_email||'system'}</p>{safeEntries.length>0 ? <dl className="timeline-detail-grid">{safeEntries.map(([key,value])=><div key={key}><dt>{String(key).replace(/_/g,' ')}</dt><dd>{typeof value==='object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>)}</dl> : detail?.description ? <p>{String(detail.description)}</p> : null}
          </div>
        </li>;
      })}</ol>
    </div>
    <p className="muted">This view displays persisted audit events, not model private reasoning. Event timestamps are shown as recorded by the source service.</p>
  </section>;
}
