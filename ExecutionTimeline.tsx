import { useMemo } from 'react';
import { BryntumScheduler } from '@bryntum/scheduler-react-community';
import { api } from '../lib/api';
import { useEffect, useState } from 'react';
import '@bryntum/scheduler-community/scheduler.css';
import '@bryntum/scheduler-community/svalbard.css';

type AuditRow = { id:number; event:string; actor:string; entity:string; detail:string; created_at:string };

export default function ExecutionTimeline(){
  const [rows,setRows]=useState<AuditRow[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(true);
  const load=()=>{setBusy(true);api<AuditRow[]>('/api/audit').then(setRows).catch((e:any)=>setError(e.message)).finally(()=>setBusy(false));};
  useEffect(()=>{load();const timer=window.setInterval(load,15000);return()=>window.clearInterval(timer);},[]);
  const schedulerProps=useMemo(()=>{
    const valid=rows.map((r)=>({...r,when:new Date(r.created_at)})).filter((r)=>!Number.isNaN(r.when.getTime()));
    const actors=Array.from(new Set(valid.map(r=>r.actor||'system')));
    const resources=actors.map((name)=>({id:name,name:name.toUpperCase()}));
    const events=valid.map((r)=>({id:String(r.id),resourceId:r.actor||'system',name:(r.event||'EVENT').replaceAll('_',' '),startDate:r.when,endDate:new Date(r.when.getTime()+15*60*1000),eventColor:(r.event||'').includes('FAILED')?'red':(r.event||'').includes('COMPLETED')?'green':'blue',tooltip:`${r.event} · ${r.entity||'system'} · ${r.detail||''}`}));
    const start=valid.length?new Date(Math.min(...valid.map(r=>r.when.getTime()))):new Date(Date.now()-86400000);
    const end=valid.length?new Date(Math.max(...valid.map(r=>r.when.getTime()))+86400000):new Date(Date.now()+86400000);
    return {startDate:start,endDate:end,viewPreset:'hourAndDay',rowHeight:48,barMargin:7,columns:[{text:'Execution stream',field:'name',width:190}],resources,events,readOnly:true};
  },[rows]);
  return <section className="page"><div className="page-heading"><div><h1>Execution timeline</h1><p>Chronological operational events mapped into a resource timeline. Refreshes every 15 seconds.</p></div><button className="secondary" onClick={load}>Refresh</button></div>{error&&<div className="error">{error}</div>}{busy&&<p className="muted">Loading audit events…</p>}{!busy&&!rows.length&&!error&&<div className="panel"><p className="muted">No audit events have been recorded yet.</p></div>}<div className="panel bryntum-panel"><div className="panel-head"><h3>MerchantOS operational event stream</h3><span className="muted">{rows.length} audit events · Bryntum Scheduler Community</span></div><div className="bryntum-timeline"><BryntumScheduler {...schedulerProps}/></div></div><p className="muted">This view displays persisted audit events, not model private reasoning. Event bars are visualized as 15-minute markers; source timestamps remain unchanged.</p></section>;
}
