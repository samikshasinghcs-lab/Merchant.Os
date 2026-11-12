import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../lib/api';
import {
  Activity, AlertCircle, ArrowRight, BookOpenCheck, Boxes, Calculator,
  RefreshCw, ShieldCheck, Wallet
} from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, RowClickedEvent } from 'ag-grid-community';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';

ModuleRegistry.registerModules([AllCommunityModule]);

type AnyRecord = Record<string, any>;

const chip = (params: { value?: unknown }) => {
  if (params.value === null || params.value === undefined || params.value === '') return null;
  const value = String(params.value);
  const kind = value.split(/[:\s_]/)[0].toLowerCase();
  return <span className={`fl-chip fl-chip-${kind}`}>{value}</span>;
};

const asObject = (value: unknown): AnyRecord =>
  value && typeof value === 'object' ? value as AnyRecord : {};

const asArray = (value: unknown): AnyRecord[] =>
  Array.isArray(value) ? value as AnyRecord[] : [];

const money = (value: unknown) =>
  Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

const blankCase = {
  order_id: '',
  case_type: 'RETURN',
  reason: '',
  complaint_cluster_id: '',
  requested_amount: '0',
  estimated_loss: '0',
  recoverable_inventory_estimate: '0',
  return_reason_code: ''
};

function Field({
  label, value, onChange, type = 'text', required = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="fl-field">
      {label}
      <input required={required} type={type} value={value}
        onChange={event => onChange(event.target.value)} />
    </label>
  );
}

export default function FinancialLifecycle() {
  const [overview, setOverview] = useState<AnyRecord | null>(null);
  const [cases, setCases] = useState<AnyRecord[]>([]);
  const [intel, setIntel] = useState<AnyRecord>({});
  const [recon, setRecon] = useState<AnyRecord | null>(null);
  const [clusters, setClusters] = useState<AnyRecord | null>(null);
  const [orders, setOrders] = useState<AnyRecord[]>([]);
  const [selected, setSelected] = useState<AnyRecord | undefined>(undefined);
  const [form, setForm] = useState(blankCase);
  const [quickSearch, setQuickSearch] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [clusterBusy, setClusterBusy] = useState(false);
  const gridRef = useRef<AgGridReact<AnyRecord>>(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const [o, c, i, r, ord, cl] = await Promise.all([
        api('/api/v1/financial-lifecycle/overview'),
        api('/api/v1/financial-lifecycle/cases'),
        api('/api/v1/financial-lifecycle/intelligence'),
        api('/api/v1/financial-lifecycle/reconciliation'),
        api('/api/v1/domain/orders'),
        api('/api/v1/financial-lifecycle/complaint-clusters?threshold=0.15')
      ]);
      setOverview(asObject(o));
      setCases(asArray(c));
      setIntel(asObject(i));
      setRecon(asObject(r));
      setOrders(asArray(ord));
      setClusters(asObject(cl));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Financial lifecycle load failed.');
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const columnDefs = useMemo<ColDef<AnyRecord>[]>(() => [
    { field: 'id', headerName: 'Case ID', minWidth: 150, valueFormatter: params => params.value ? `CASE-${String(params.value).slice(0, 8).toUpperCase()}` : '' },
    { field: 'case_type', headerName: 'Type', cellRenderer: chip },
    { field: 'customer', headerName: 'Customer' },
    { field: 'product', headerName: 'Product' },
    { field: 'batch', headerName: 'Batch' },
    { field: 'order_id', headerName: 'Order' },
    { field: 'amount', headerName: 'Amount' },
    { field: 'status', headerName: 'Status', cellRenderer: chip },
    { field: 'policy_result', headerName: 'Policy result', cellRenderer: chip, minWidth: 180 },
    { field: 'ai_suggestion', headerName: 'AI suggestion', cellRenderer: chip },
    { field: 'evidence_count', headerName: 'Evidence' },
    { field: 'net_result', headerName: 'Net result (estimate)' },
    { field: 'decision', headerName: 'Decision', cellRenderer: chip },
    { field: 'decided_by', headerName: 'Decided by' }
  ], []);

  async function submit(path: string, method: string, body: AnyRecord) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await api(path, { method, body: JSON.stringify(body) });
      const summary = [result.message, result.note, result.status, result.decision, result.id ? `Reference ${String(result.id).slice(0, 12)}` : ''].filter(Boolean).join(' · ');
      setMessage(summary || 'Request completed.');
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed.');
    } finally {
      setBusy(false);
    }
  }

  async function runClustering() {
    setClusterBusy(true);
    setError('');
    try {
      const result = asObject(await api(
        '/api/v1/financial-lifecycle/complaint-clusters/run',
        { method: 'POST', body: JSON.stringify({ threshold: 0.15 }) }
      ));
      setClusters(result);
      setMessage(`Clustered ${result.review_count ?? 0} reviews using ${result.method ?? 'reported method'}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Clustering failed.');
    } finally {
      setClusterBusy(false);
    }
  }

  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submit('/api/v1/financial-lifecycle/cases', 'POST', form);
    setForm(blankCase);
  }

  const batchRows = Object.entries(asObject(intel?.by_batch));
  const weeklyRows = Object.entries(asObject(intel?.by_week));
  const productRows = Object.entries(asObject(intel?.by_product));
  const reasonRows = Object.entries(asObject(intel?.cost_by_reason));

  return (
    <main className="financial-lifecycle">
      <style>{`
        .financial-lifecycle{display:grid;gap:18px;color:var(--text,#172033);min-width:0}
        .fl-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
        .fl-kicker{font-size:10px;letter-spacing:.14em;font-weight:800;color:#64748b}
        .fl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;min-width:0}
        .fl-card{background:var(--panel,#fff);border:1px solid var(--border,#e2e8f0);border-radius:15px;padding:17px;min-width:0}
        .fl-card h3{margin:0 0 12px;font-size:16px}
        .fl-metric{font-size:26px;font-weight:800;margin:7px 0}
        .fl-muted{color:#64748b;font-size:12px}
        .fl-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
        .fl-field{display:grid;gap:6px;font-size:12px;font-weight:700;min-width:0}
        .fl-field input,.fl-field select,.fl-field textarea{width:100%;max-width:100%;box-sizing:border-box;border:1px solid var(--border,#cbd5e1);border-radius:8px;padding:10px;background:var(--surface,#fff);color:inherit}
        .fl-wide{grid-column:1/-1}
        .fl-btn{border:0;border-radius:8px;background:#172554;color:#fff;padding:10px 14px;font-weight:700;cursor:pointer}
        .fl-btn:disabled{opacity:.5;cursor:not-allowed}
        .fl-notice{padding:12px;border-radius:9px;background:#ecfdf5;color:#166534;overflow-wrap:anywhere}
        .fl-error{padding:12px;border-radius:9px;background:#fef2f2;color:#991b1b;overflow-wrap:anywhere}
        .fl-scroll{width:100%;overflow-x:auto}
        .fl-invest-box{border:1px solid var(--border,#e2e8f0);border-radius:12px;padding:13px;min-width:0}
        .fl-invest-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
        .fl-decision-sticky{position:relative;bottom:auto;background:var(--panel,#fff);border:1px solid var(--border,#cbd5e1);box-shadow:0 8px 30px #0f172a20;border-radius:13px;padding:12px;z-index:1}
        @media(max-width:640px){.fl-invest-grid,.fl-form{grid-template-columns:1fr}.fl-decision-sticky{position:relative;bottom:auto}}
      `}</style>

      <header className="fl-head">
        <div>
          <div className="fl-kicker">SANDBOX / FINANCIAL LIFECYCLE</div>
          <h1 style={{ margin: '7px 0' }}>Financial command centre</h1>
          <p className="fl-muted">Costs, returns, exchanges, inventory disposition and accounting. Estimates are distinct from verified outcomes.</p>
        </div>
        <button className="fl-btn" onClick={() => void load()}><RefreshCw size={14} /> Refresh</button>
      </header>

      {error && <div role="alert" className="fl-error"><AlertCircle size={15} /> {error}</div>}
      {message && <div role="status" className="fl-notice">{message}</div>}

      <section className="fl-grid" aria-label="Financial summary">
        <article className="fl-card"><span className="fl-muted">ORDERS</span><div className="fl-metric">{overview?.order_count ?? '—'}</div><span className="fl-muted">Tenant-scoped orders</span></article>
        <article className="fl-card"><span className="fl-muted">RESOLUTION CASES</span><div className="fl-metric">{overview?.case_count ?? '—'}</div><span className="fl-muted">{overview?.open_cases ?? '—'} open</span></article>
        <article className="fl-card"><span className="fl-muted">COST COVERAGE</span><div className="fl-metric">{overview?.cost_coverage ?? '—'}</div><span className="fl-muted">Orders with cost entries</span></article>
        <article className="fl-card"><span className="fl-muted">JOURNAL ENTRIES</span><div className="fl-metric">{overview?.journal_entries ?? '—'}</div><span className="fl-muted">Balanced entries only</span></article>
      </section>

      <section className="fl-card" aria-label="Tenant complaint clustering">
        <div className="fl-head">
          <div><h3>Complaint clustering · tenant scoped</h3><p className="fl-muted">TF-IDF fallback / optional embeddings as configured by the backend. Similarity is not causation.</p></div>
          <button className="fl-btn" disabled={clusterBusy} onClick={() => void runClustering()}>{clusterBusy ? 'Clustering…' : 'Run complaint clustering'}</button>
        </div>
        {clusters && <>
          <p className="fl-muted">{clusters.review_count ?? 0} reviews · method: {clusters.method ?? 'unknown'} · {clusters.scope ?? 'tenant scope'} · external processing: {String(clusters.external_processing ?? 'not reported')}</p>
          <div className="fl-grid">{asArray(clusters.clusters).map(cluster => (
            <article className="fl-card" key={String(cluster.cluster_id)}>
              <b>{cluster.cluster_id}</b><div className="fl-metric">{cluster.count ?? 0}</div>
              <p className="fl-muted">Keywords: {asArray(cluster.keywords).join(', ') || 'No dominant terms'}</p>
              {asArray(cluster.examples).map((example, index) => <p className="fl-muted" key={index}>{String(example)}</p>)}
            </article>
          ))}</div>
          <small className="fl-muted">{clusters.caveat ?? ''}</small>
        </>}
      </section>

      <section className="fl-grid" aria-label="Case performance summary">
        <article className="fl-card"><span className="fl-muted">OPEN CASES</span><div className="fl-metric">{cases.filter(item => !['COMPLETED', 'CANCELLED', 'REJECTED'].includes(String(item.status))).length}</div><span className="fl-muted">Awaiting resolution</span></article>
        <article className="fl-card"><span className="fl-muted">REFUND / RETURN CASES · 7 DAYS</span><div className="fl-metric">{cases.filter(item => ['REFUND', 'RETURN'].includes(String(item.case_type)) && item.created_at && Date.now() - new Date(String(item.created_at)).getTime() < 7 * 86400000).length}</div><span className="fl-muted">Created in last 7 days; not provider-settled count</span></article>
        <article className="fl-card"><span className="fl-muted">ESTIMATED NET LOSS</span><div className="fl-metric">{money(cases.reduce((total, item) => total + Number(item.estimated_loss || 0), 0))}</div><span className="fl-muted">Merchant estimates; currencies not consolidated</span></article>
        <article className="fl-card"><span className="fl-muted">WORST BATCH</span><div className="fl-metric">{batchRows.sort((a, b) => Number(asObject(b[1]).estimated_loss || 0) - Number(asObject(a[1]).estimated_loss || 0))[0]?.[0] ?? '—'}</div><span className="fl-muted">Highest estimated loss in available data</span></article>
      </section>

      <section className="fl-card">
        <h3><Boxes size={17} /> Open a resolution case</h3>
        <form className="fl-form" onSubmit={event => void createCase(event)}>
          <label className="fl-field fl-wide">Order
            <select required value={form.order_id} onChange={event => setForm({ ...form, order_id: event.target.value })}>
              <option value="">Select order</option>
              {orders.map(order => <option key={String(order.id)} value={String(order.id)}>{order.id} · {order.product || 'Order'}</option>)}
            </select>
          </label>
          <label className="fl-field">Case type
            <select value={form.case_type} onChange={event => setForm({ ...form, case_type: event.target.value })}>
              {['CANCELLATION', 'RETURN', 'REFUND', 'EXCHANGE'].map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}
            </select>
          </label>
          <Field label="Reason" value={form.reason} onChange={value => setForm({ ...form, reason: value })} />
          <Field label="Complaint cluster ID (optional)" value={form.complaint_cluster_id} onChange={value => setForm({ ...form, complaint_cluster_id: value })} />
          <Field label="Requested amount" type="number" value={form.requested_amount} onChange={value => setForm({ ...form, requested_amount: value })} />
          <Field label="Estimated loss" type="number" value={form.estimated_loss} onChange={value => setForm({ ...form, estimated_loss: value })} />
          <Field label="Recoverable inventory estimate" type="number" value={form.recoverable_inventory_estimate} onChange={value => setForm({ ...form, recoverable_inventory_estimate: value })} />
          <Field label="Return reason code" value={form.return_reason_code} onChange={value => setForm({ ...form, return_reason_code: value })} />
          <button className="fl-btn" disabled={busy || !form.order_id}>Create case</button>
        </form>
      </section>

      <section className="fl-card">
        <h3><Activity size={17} /> Cases workspace · AG Grid</h3>
        <p className="fl-muted">Select a row to investigate. Sort, filter, quick search and CSV export are enabled.</p>
        <div className="fl-form" style={{ marginBottom: 10 }}>
          <Field label="Quick search" value={quickSearch} onChange={setQuickSearch} />
          {['OPEN', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'].map(status => <button key={status} type="button" className="fl-btn" onClick={() => setQuickSearch(status)}>{status}</button>)}
          <button type="button" className="fl-btn" onClick={() => setQuickSearch('')}>Clear</button>
          <button type="button" className="fl-btn" onClick={() => gridRef.current?.api?.exportDataAsCsv()}>Export CSV</button>
          <button type="button" className="fl-btn" onClick={() => {
            try { localStorage.setItem('merchantos.savedFilter', JSON.stringify({ filters: gridRef.current?.api?.getFilterModel() ?? {}, search: quickSearch })); } catch { /* storage may be disabled */ }
          }}>Save filter</button>
          <button type="button" className="fl-btn" onClick={() => {
            try {
              const saved = JSON.parse(localStorage.getItem('merchantos.savedFilter') || 'null') as AnyRecord | null;
              if (saved) { gridRef.current?.api?.setFilterModel(saved.filters ?? {}); setQuickSearch(String(saved.search ?? '')); }
            } catch { setError('Saved filter could not be loaded.'); }
          }}>Load filter</button>
        </div>
        <div className="fl-scroll">
          <div style={{ height: 440, width: '100%', minWidth: 900 }}>
            <AgGridReact<AnyRecord>
              ref={gridRef}
              rowData={cases}
              columnDefs={columnDefs}
              quickFilterText={quickSearch}
              defaultColDef={{ sortable: true, filter: true, resizable: true, floatingFilter: true }}
              rowSelection={{ mode: 'singleRow' }}
              onRowClicked={(event: RowClickedEvent<AnyRecord>) => setSelected(event.data)}
              animateRows
            />
          </div>
        </div>
        {selected && <CaseInvestigation selected={selected} onRefresh={load} onMessage={setMessage} onError={setError} />}
      </section>

      <section className="fl-card">
        <h3><Activity size={17} /> Financial intelligence</h3>
        <p className="fl-muted">Batch signals are exploratory: correlation, not proven cause. Small samples and incomplete data can distort results.</p>
        <div className="fl-grid">{Object.entries(asObject(intel?.batch_statistics)).map(([name, value]) => {
          const item = asObject(value);
          return <article className="fl-invest-box" key={name}><b>Batch {name}</b><p>Complaint rate: {(Number(item.complaint_rate || 0) * 100).toFixed(1)}%</p><p>Baseline: {(Number(item.baseline_rate_excluding_batch || 0) * 100).toFixed(1)}%</p><p>Lift: {item.lift ?? 'N/A'} · Fisher p: {item.fisher_exact_two_sided_p ?? 'N/A'}</p><small className="fl-muted">{item.interpretation ?? 'Correlation, not proven cause.'}</small></article>;
        })}</div>
        <h4>Estimated loss by batch</h4>
        {batchRows.length ? batchRows.map(([name, value]) => <p key={name}>{name}: {money(asObject(value).estimated_loss)}</p>) : <p className="fl-muted">No batch loss data.</p>}
        <h4>Cost by reason</h4>
        <div className="fl-grid">{reasonRows.map(([name, value]) => <article className="fl-invest-box" key={name}><b>{name}</b><p>Cases: {asObject(value).case_count ?? 0}</p><p>Estimated loss: {money(asObject(value).estimated_loss)}</p></article>)}</div>
        <h4>Product and weekly roll-ups</h4>
        <div className="fl-grid">{[...productRows, ...weeklyRows].map(([name, value], index) => <article className="fl-invest-box" key={`${index}-${name}`}><b>{name}</b><p>{asObject(value).case_count ?? 0} cases · estimated {money(asObject(value).estimated_loss)}</p></article>)}</div>
        <h4>Return-rate anomaly signals</h4>
        <div className="fl-invest-grid">{Object.entries(asObject(asObject(intel?.anomaly_signals).customer)).map(([customerId, value]) => { const signal = asObject(value); return <article className="fl-invest-box" key={customerId}><b>{customerId}</b><p>{signal.complaint_orders ?? 0} complaints / {signal.orders ?? 0} orders</p><p>Complaint rate: {(Number(signal.rate ?? 0) * 100).toFixed(1)}%</p><p>Z-score: {signal.z_score ?? '—'} · Isolation Forest: {signal.isolation_forest_score ?? 'Not calculated'}</p><small className="fl-muted">Exploratory signal only; not proof of abuse.</small></article>; })}</div><p className="fl-muted">{asObject(intel?.anomaly_signals).method ?? 'No anomaly method reported.'}</p>
        <h4>Repeat-returner signals</h4>
        {asArray(intel?.repeat_returners).length ? asArray(intel?.repeat_returners).map(item => <p key={String(item.customer_id)}>{item.customer_id} · {item.case_count} cases · signal only</p>) : <p className="fl-muted">No repeat-returner signals in available records.</p>}
      </section>

      <section className="fl-card">
        <h3><ShieldCheck size={17} /> Execution-to-ledger reconciliation</h3>
        <p className="fl-muted">Compares MerchantOS PayPal execution records with linked journal entries. Not bank reconciliation.</p>
        <div className="fl-grid"><div><b>{recon?.matched ?? 0}</b><div className="fl-muted">Matched</div></div><div><b>{recon?.unmatched ?? 0}</b><div className="fl-muted">Missing journal link</div></div></div>
        {asArray(recon?.items).length ? <div className="fl-scroll"><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}><thead><tr><th align="left">Execution</th><th align="left">Journal</th><th align="left">Status</th><th align="right">Amount</th></tr></thead><tbody>{asArray(recon?.items).map((item, index) => <tr key={String(item.id ?? index)}><td>{item.execution_id ?? item.refund_id ?? item.id ?? '—'}</td><td>{item.journal_entry_id ?? item.journal_id ?? 'Missing'}</td><td>{item.status ?? (item.matched ? 'Matched' : 'Unmatched')}</td><td align="right">{item.currency ?? ''} {item.amount ?? '—'}</td></tr>)}</tbody></table></div> : <p className="fl-muted">No PayPal execution records are available to reconcile yet.</p>}
      </section>
      <p className="fl-muted">Refunds remain in the existing separate PayPal approval and execution workflow. This screen does not independently move money or mutate warehouse stock.</p>
    </main>
  );
}
      type InvestigationProps = {
  selected: AnyRecord;
  onRefresh: () => Promise<void>;
  onMessage: (value: string) => void;
  onError: (value: string) => void;
};

function CaseInvestigation({ selected, onRefresh, onMessage, onError }: InvestigationProps) {
  const [detail, setDetail] = useState<AnyRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [reasonCode, setReasonCode] = useState('');
  const [otherReason, setOtherReason] = useState('');
  const [decisionNote, setDecisionNote] = useState('');
  const [evidenceType, setEvidenceType] = useState('product_photo');
  const [evidenceDescription, setEvidenceDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [policy, setPolicy] = useState<AnyRecord | null>(null);
  const [days, setDays] = useState('0');
  const [overrideReason, setOverrideReason] = useState('');
  const [hygiene, setHygiene] = useState(false);
  const [shipped, setShipped] = useState(false);
  const [previousExchange, setPreviousExchange] = useState(false);
  const [approval, setApproval] = useState<AnyRecord | null>(null);
  const [workflowRun, setWorkflowRun] = useState<AnyRecord | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [disposition, setDisposition] = useState('RESTOCK');
  const [repairCost, setRepairCost] = useState('0');
  const [returnShipping, setReturnShipping] = useState('0');
  const [handling, setHandling] = useState('0');
  const [writeOff, setWriteOff] = useState('0');
  const [supplierCredit, setSupplierCredit] = useState('0');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api(`/api/v1/financial-lifecycle/cases/${selected.id}/detail`);
      setDetail(asObject(result));
      if (['REFUND', 'RETURN'].includes(String(selected.case_type))) {
        const approvalRows = asArray(await api('/api/v1/operations/financial/refund-approvals'));
        const requestKey = `case-${String(selected.id).replaceAll('-', '')}`;
        setApproval(approvalRows.find(item => item.request_key === requestKey) ?? null);
      }
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Case detail failed to load.');
    } finally {
      setLoading(false);
    }
  }, [selected.id, onError]);

  useEffect(() => {
    void refresh();
    setPolicy(null);
    setApproval(null);
    setWorkflowRun(null);
  }, [refresh]);

  useEffect(() => {
    let active = true;
    const urls: Record<string, string> = {};
    const evidence = asArray(detail?.evidence);
    void (async () => {
      for (const item of evidence) {
        if (!item.download_url || !['product_photo', 'customer_screenshot'].includes(String(item.type))) continue;
        try {
          const base = import.meta.env.VITE_API_BASE ?? '';
          const response = await fetch(`${base}${item.download_url}`, {
            headers: { Authorization: `Bearer ${localStorage.getItem('merchantos_token') || ''}` }
          });
          if (response.ok) {
            urls[String(item.id)] = URL.createObjectURL(await response.blob());
            if (active) setPreviews({ ...urls });
          }
        } catch { /* private preview is optional */ }
      }
    })();
    return () => {
      active = false;
      Object.values(urls).forEach(url => URL.revokeObjectURL(url));
    };
  }, [detail?.evidence]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    onError('');
    try {
      const body = new FormData();
      body.set('file', file);
      body.set('evidence_type', evidenceType);
      body.set('description', evidenceDescription);
      const result = asObject(await api(`/api/v1/financial-lifecycle/cases/${selected.id}/evidence`, { method: 'POST', body }));
      onMessage(`Evidence ${result.id ?? ''} uploaded. Integrity status is supplied by the server.`);
      setFile(null);
      setEvidenceDescription('');
      await refresh();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Evidence upload failed.');
    } finally {
      setBusy(false);
    }
  }

  async function assessPolicy() {
    if (!detail) return;
    setBusy(true);
    try {
      const order = asObject(detail.order);
      const result = await api('/api/v1/financial-lifecycle/policy/assess', {
        method: 'POST',
        body: JSON.stringify({
          case_type: selected.case_type,
          days_since_delivery: Number(days),
          captured_amount: order.amount ?? 0,
          requested_amount: selected.requested_amount ?? 0,
          previous_exchange_for_order: previousExchange,
          hygiene_item_opened: hygiene,
          shipped,
          override_reason: overrideReason
        })
      });
      setPolicy(asObject(result));
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Policy assessment failed.');
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: 'APPROVE' | 'REJECT') {
    setBusy(true);
    onError('');
    try {
      const result = asObject(await api(`/api/v1/financial-lifecycle/cases/${selected.id}/decision`, {
        method: 'POST',
        body: JSON.stringify({ decision, reason_code: reasonCode, other_reason: otherReason, decision_note: decisionNote })
      }));
      onMessage(`${result.decision ?? decision} recorded. ${result.note ?? ''}`);
      await refresh();
      await onRefresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Decision could not be recorded.');
    } finally {
      setBusy(false);
    }
  }

  async function requestRefundApproval() {
    setBusy(true);
    try {
      const result = asObject(await api(`/api/v1/financial-lifecycle/cases/${selected.id}/refund-approval`, {
        method: 'POST', body: JSON.stringify({})
      }));
      setApproval({ ...result, id: result.approval_id ?? result.id });
      onMessage(`Linked PayPal approval request ${result.approval_id ?? result.id ?? ''} · ${result.status ?? ''}. Independent approval is still required.`);
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Refund approval request failed.');
    } finally {
      setBusy(false);
    }
  }

  async function reconcileRefund() {
    if (!approval?.id) return;
    setBusy(true);
    try {
      const result = asObject(await api(`/api/v1/operations/financial/refund-approvals/${approval.id}/reconcile`, { method: 'POST', body: JSON.stringify({}) }));
      setApproval({ ...approval, ...result });
      onMessage(`PayPal capture reconciliation: ${result.status ?? 'checked'}.`);
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'PayPal reconciliation failed.');
    } finally { setBusy(false); }
  }

  async function decideRefund(decision: 'APPROVE' | 'REJECT') {
    if (!approval?.id) return;
    setBusy(true);
    try {
      const result = asObject(await api(`/api/v1/operations/financial/refund-approvals/${approval.id}/decision`, {
        method: 'POST', body: JSON.stringify({ decision, note: 'Reviewed customer complaint in MerchantOS.' })
      }));
      setApproval({ ...approval, ...result });
      onMessage(`Independent refund decision: ${result.status ?? decision}. ${result.note ?? ''}`);
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Independent approval failed. The requester cannot approve their own request.');
    } finally { setBusy(false); }
  }

  async function executeRefund() {
    if (!approval?.id) return;
    setBusy(true);
    try {
      const result = asObject(await api(`/api/v1/operations/financial/refund-approvals/${approval.id}/execute`, { method: 'POST', body: JSON.stringify({}) }));
      setApproval({ ...approval, execution: result, status: result.status === 'SUCCEEDED' ? 'EXECUTED' : approval.status });
      onMessage(`PayPal Sandbox refund: ${result.provider_status ?? result.status ?? 'UNKNOWN'} · Refund ID: ${result.provider_refund_id ?? 'not confirmed'}`);
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'PayPal Sandbox refund execution failed.');
    } finally { setBusy(false); }
  }

  async function runWorkflow() {
    setBusy(true);
    try {
      const result = asObject(await api(`/api/v1/financial-lifecycle/cases/${selected.id}/run-workflow`, {
        method: 'POST', body: JSON.stringify({})
      }));
      setWorkflowRun(result);
      onMessage(`Render workflow ${result.run_id ?? ''} dispatched. No financial action was attempted.`);
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Workflow dispatch failed.');
    } finally {
      setBusy(false);
    }
  }

  if (loading && !detail) return <div className="fl-card">Loading case investigation…</div>;
  if (!detail) return <div className="fl-card">Case detail could not be loaded.</div>;

  const caseData = asObject(detail.case);
  const order = asObject(detail.order);
  const originalCaptureId = String(order.capture_id || '');
  const signals = asObject(detail.signals);
  const ai = asObject(detail.computed_recommendation);
  const evidence = asArray(detail.evidence);
  const costs = asObject(detail.costs);
  const cogs = Number(costs.cogs || 0);
  const rate = disposition === 'RESTOCK' ? 1
    : disposition === 'OPEN_BOX' ? Number(import.meta.env.VITE_OPEN_BOX_RECOVERY_RATE || 0.7)
    : disposition === 'REFURBISH' ? Number(import.meta.env.VITE_REFURBISH_RECOVERY_RATE || 0.6) : 0;
  const recovered = disposition === 'RETURN_TO_SUPPLIER' ? Number(supplierCredit)
    : disposition === 'WRITE_OFF' ? 0
    : Math.max(0, cogs * rate - (disposition === 'REFURBISH' ? Number(repairCost) : 0));
  const net = recovered - Number(selected.requested_amount || 0) - Number(returnShipping)
    - Number(handling) - Number(costs.payment_fee || 0) - Number(writeOff);
  const canDecide = !busy && evidence.length > 0 && decisionNote.trim().length >= 5
    && reasonCode.length > 0 && (reasonCode !== 'OTHER' || otherReason.trim().length >= 5);

  return (
    <section className="fl-card" style={{ marginTop: 14, display: 'grid', gap: 14 }}>
      <header className="fl-head">
        <div><div className="fl-kicker">CASE INVESTIGATION · SANDBOX / DEMO DATA</div><h2>Case CASE-{String(caseData.id ?? selected.id).slice(0, 8).toUpperCase()}</h2><small className="fl-muted">Internal reference: {caseData.id ?? selected.id}</small><span className="fl-muted">{caseData.case_type ?? selected.case_type} · {caseData.status ?? selected.status} · Order {caseData.order_id ?? selected.order_id}</span></div>
        <span className="fl-muted">AI: computed rules · not an accuracy claim</span>
      </header>

      <div className="fl-invest-grid">
        <article className="fl-invest-box"><h4>Order & customer</h4><p><b>{order.customer_name || order.customer_id || 'Unknown customer'}</b></p><p>{order.product || 'Product not recorded'} · Batch {order.batch || 'not recorded'}</p><p>Paid: {order.currency ?? ''} {order.amount ?? '—'}</p><p>Order date: {order.created_at || 'Not recorded'}</p><p>Delivery date: {order.delivery_date || 'Not recorded'}</p><p>Payment: {order.payment_status || 'Unknown'} · Capture linked: {order.capture_id_present ? 'Yes' : 'No'}</p></article>
        <article className="fl-invest-box"><h4>Customer complaint</h4>{asArray(detail.complaints).length ? asArray(detail.complaints).map(item => <p key={String(item.id)}>{item.message}<small className="fl-muted"> · {item.category || 'Unclassified'} / {item.severity || 'severity unknown'}</small></p>) : <p className="fl-muted">No tenant-linked review message found. Case reason: {caseData.reason || 'not recorded'}</p>}</article>
        <article className="fl-invest-box"><h4>AI recommendation · {ai.mode || 'computed'}</h4><b>{ai.recommendation || 'REVIEW'}</b><p className="fl-muted">Signal strength: {ai.signal_strength || 'not reported'} · {ai.confidence_label || 'Uncalibrated signal; not a probability'}</p>{asArray(ai.reasons).map((item, index) => <p key={index}>• {String(item)}</p>)}<p>Flags: {asArray(signals.flags).join(', ') || 'None detected from available records'}</p><details><summary>Expected-loss maths</summary>{asArray(ai.expected_loss_math).map((item, index) => <p key={index} className="fl-muted">{String(item)}</p>)}</details><p className="fl-muted">{ai.validation || 'AI advises only; deterministic policy and human approval control actions.'}</p></article>
        <article className="fl-invest-box"><h4>Expected-loss comparison</h4><p>Approve: {order.currency ?? ''} {ai.expected_loss_estimates?.approve ?? '—'}</p><p>Reject: {order.currency ?? ''} {ai.expected_loss_estimates?.reject ?? '—'}</p><p>Exchange: {order.currency ?? ''} {ai.expected_loss_estimates?.exchange ?? '—'}</p></article>
      </div>

      <article className="fl-invest-box">
        <h4>Deterministic policy check</h4>
        <div className="fl-form">
          <Field label="Days since delivery" type="number" value={days} onChange={setDays} />
          <label className="fl-field"><span><input type="checkbox" checked={previousExchange} onChange={event => setPreviousExchange(event.target.checked)} /> Previous exchange</span></label>
          <label className="fl-field"><span><input type="checkbox" checked={hygiene} onChange={event => setHygiene(event.target.checked)} /> Opened hygiene item</span></label>
          <label className="fl-field"><span><input type="checkbox" checked={shipped} onChange={event => setShipped(event.target.checked)} /> Already shipped</span></label>
          <label className="fl-field fl-wide">Override reason<textarea value={overrideReason} onChange={event => setOverrideReason(event.target.value)} /></label>
          <button type="button" className="fl-btn" disabled={busy} onClick={() => void assessPolicy()}>Run policy check</button>
        </div>
        {policy && <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(policy, null, 2)}</pre>}
        <small className="fl-muted">Policy inputs must be checked against authoritative fulfilment records. Overrides require a reason and server-side audit.</small>
      </article>

      <article className="fl-invest-box">
        <h4>Evidence vault · server enforces file type, size and count limits</h4>
        <form className="fl-form" onSubmit={event => void upload(event)}>
          <label className="fl-field">Evidence type<select value={evidenceType} onChange={event => setEvidenceType(event.target.value)}>{[['product_photo', 'Product photo'], ['courier_receipt', 'Courier receipt'], ['customer_screenshot', 'Customer screenshot'], ['order_document', 'Order document'], ['other', 'Other']].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <Field label="Evidence description (min 5 characters)" value={evidenceDescription} onChange={setEvidenceDescription} required />
          <label className="fl-field">File (JPEG, PNG or PDF)<input type="file" accept="image/jpeg,image/png,application/pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
          <button className="fl-btn" disabled={busy || !file || evidenceDescription.trim().length < 5}>Upload & verify</button>
        </form>
        <div className="fl-invest-grid">{evidence.map(item => <article className="fl-invest-box" key={String(item.id)}><b>✓ {item.type}</b>{previews[String(item.id)] && <img src={previews[String(item.id)]} alt={`Evidence ${item.type}`} style={{ display: 'block', maxWidth: '100%', maxHeight: 150, objectFit: 'contain', margin: '8px 0' }} />}<p>{item.description}</p><small className="fl-muted">{item.integrity_status} · SHA-256 {String(item.sha256 || 'not available').slice(0, 16)}…</small></article>)}</div>
        {!evidence.length && <div className="fl-notice" style={{ marginTop: 10 }}>Decision locked: upload at least one evidence file, add a decision note of 5+ characters, and choose a reason code. The server also enforces its own checks.</div>}
      </article>

      <article className="fl-invest-box">
        <h4>Disposition & live P&L preview</h4>
        <div className="fl-form">
          <label className="fl-field">Disposition<select value={disposition} onChange={event => setDisposition(event.target.value)}>{['RESTOCK', 'OPEN_BOX', 'REFURBISH', 'RETURN_TO_SUPPLIER', 'WRITE_OFF'].map(value => <option key={value}>{value}</option>)}</select></label>
          <Field label="Repair cost" type="number" value={repairCost} onChange={setRepairCost} />
          <Field label="Return shipping" type="number" value={returnShipping} onChange={setReturnShipping} />
          <Field label="Handling" type="number" value={handling} onChange={setHandling} />
          <Field label="Write-off" type="number" value={writeOff} onChange={setWriteOff} />
          <Field label="Supplier credit" type="number" value={supplierCredit} onChange={setSupplierCredit} />
        </div>
        <p><b>Recovered item value:</b> {order.currency ?? ''} {recovered.toFixed(2)} · <b>Estimated net:</b> {order.currency ?? ''} {net.toFixed(2)}</p>
        <small className="fl-muted">Based on merchant-entered COGS and estimated costs. PayPal fee treatment must be checked against merchant terms.</small>
        <button type="button" className="fl-btn" disabled={busy} onClick={() => void submitDisposition()}>Record disposition instruction</button>
      </article>

      <article className="fl-invest-box">
        <h4>Recorded inventory disposition</h4>
        {asArray(detail.dispositions).length ? asArray(detail.dispositions).map((item, index) => <p key={String(item.id || index)}><b>{String(item.disposition).replaceAll('_',' ')}</b> · Qty {item.quantity} · Estimated recovery {order.currency ?? ''} {item.estimated_recovery} {item.realized_recovery != null ? `· Verified recovery ${order.currency ?? ''} ${item.realized_recovery}` : '· Actual recovery not verified'}<small className="fl-muted"> · {item.created_at ? new Date(item.created_at).toLocaleString() : 'Date unavailable'}</small></p>) : <p className="fl-muted">No disposition instruction recorded yet.</p>}
      </article>

      <article className="fl-invest-box">
        <h4>Render resolution workflow</h4>
        <p className="fl-muted">Advisory analysis only. It cannot approve or execute payments.</p>
        <button type="button" className="fl-btn" disabled={busy} onClick={() => void runWorkflow()}>Run resolution workflow</button>
        {workflowRun && <p>Run ID: <b>{workflowRun.run_id}</b> · {workflowRun.status} {workflowRun.url && <a href={workflowRun.url} target="_blank" rel="noreferrer">Open run ↗</a>}</p>}
      </article>

      <article className="fl-invest-box"><h4>Audit trail</h4>{asArray(detail.events).map(item => <p key={String(item.id)}><b>{item.type}</b> · {item.created_at} · {JSON.stringify(item.payload)}</p>)}{!asArray(detail.events).length && <p className="fl-muted">No case events yet.</p>}</article>
      <article className="fl-invest-box"><h4>PayPal provider result</h4><p>Approval: {detail.paypal?.approval_status || 'Not requested'}</p><p>Refund ID: {detail.paypal?.refund_id || 'Not yet provider-confirmed'}</p><p>Provider status: {detail.paypal?.provider_status || 'Not executed'} · {detail.paypal?.environment || 'unknown'}</p><small className="fl-muted">Refund IDs appear only after the canonical execution service records a provider response. Demo remains Sandbox-only.</small></article>

      <div className="fl-decision-sticky">
        <b>Human decision · no automatic money movement</b>
        <div className="fl-form" style={{ marginTop: 10 }}>
          <label className="fl-field">Reason code<select value={reasonCode} onChange={event => setReasonCode(event.target.value)}><option value="">Choose a reason</option>{['DAMAGED', 'WRONG_ITEM', 'LATE', 'POLICY_VIOLATION', 'SUSPECTED_ABUSE', 'OTHER'].map(value => <option key={value}>{value}</option>)}</select></label>
          {reasonCode === 'OTHER' && <Field label="Other reason (required)" value={otherReason} onChange={setOtherReason} required />}
          <label className="fl-field fl-wide">Decision note<textarea value={decisionNote} onChange={event => setDecisionNote(event.target.value)} /></label>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 10 }}>
          <button className="fl-btn" disabled={!canDecide} onClick={() => void decide('APPROVE')}>Approve / propose</button>
          <button className="fl-btn" style={{ background: '#991b1b' }} disabled={!canDecide} onClick={() => void decide('REJECT')}>Reject</button>
        </div>
        <small className="fl-muted">{!evidence.length ? 'Locked: attach evidence first.' : !reasonCode ? 'Locked: choose a reason code.' : decisionNote.trim().length < 5 ? 'Locked: enter a decision note (at least 5 characters).' : 'Ready for human review.'} Approval is a proposal only. Refunds still require separate reconciliation, independent approver and PayPal Sandbox execution.</small>
        {['RETURN', 'REFUND'].includes(String(selected.case_type)) && <div className="fl-invest-box" style={{ marginTop: 12 }}>
          <h4>Refund destination · original payment method</h4>
          <div className="fl-invest-box" style={{marginBottom:12,background:'#f8fafc'}}>
            <b>Refund back to the payment that funded this order</b>
            <p className="fl-muted">PayPal sends a capture refund to the customer's original funding source. MerchantOS uses the verified capture ID linked to this order; do not enter a different customer or wallet ID.</p>
            <label className="fl-field">Original PayPal capture ID
              <input readOnly value={originalCaptureId} placeholder="No capture ID linked to this order" aria-label="Original PayPal capture ID" />
            </label>
            <button type="button" className="fl-btn" disabled={!originalCaptureId} onClick={() => { void navigator.clipboard?.writeText(originalCaptureId).then(() => onMessage('Original PayPal capture ID copied.')).catch(() => onError('Could not copy the capture ID; select and copy it manually.')); }}>Copy payment ID</button>
            {!originalCaptureId && <p className="fl-error">Refund blocked: this order has no recorded PayPal capture ID. Reconcile the original payment before requesting a refund.</p>}
            <p><b>Refund amount:</b> {order.currency ?? ''} {money(selected.requested_amount)} · <b>Destination:</b> Original PayPal funding source</p>
          </div>
          <h4>PayPal Sandbox refund lifecycle</h4>
          {!approval?.id && <><button type="button" className="fl-btn" disabled={busy || caseData.status !== 'UNDER_REVIEW' || !originalCaptureId || Number(selected.requested_amount) <= 0 || Number(selected.requested_amount) > Number(order.amount)} onClick={() => void requestRefundApproval()}>Create linked refund request</button>{caseData.status !== 'UNDER_REVIEW' && <small className="fl-muted">Available after the case reaches UNDER REVIEW. Current case status: {caseData.status ?? 'unknown'}.</small>}{Number(selected.requested_amount) > Number(order.amount) && <small className="fl-error">Refund amount exceeds the original captured order amount.</small>}</>}
          {approval?.id && <>
            <p className="fl-muted">Request {String(approval.id).slice(0, 8)} · {approval.status} · {approval.currency ?? detail.order?.currency ?? ''} {approval.amount ?? selected.requested_amount}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {approval.status === 'PENDING_RECONCILIATION' && <button type="button" className="fl-btn" disabled={busy} onClick={() => void reconcileRefund()}>Reconcile with PayPal</button>}
              {approval.status === 'PENDING_APPROVAL' && <><button type="button" className="fl-btn" disabled={busy} onClick={() => void decideRefund('APPROVE')}>Independent OWNER/ADMIN approve</button><button type="button" className="fl-btn" style={{ background: '#991b1b' }} disabled={busy} onClick={() => void decideRefund('REJECT')}>Reject refund</button></>}
              {approval.status === 'APPROVED' && <button type="button" className="fl-btn" disabled={busy} onClick={() => void executeRefund()}>Execute PayPal Sandbox refund</button>}
            </div>
            {approval.execution && <p><b>Provider:</b> PAYPAL SANDBOX · <b>Status:</b> {approval.execution.provider_status ?? approval.execution.status} · <b>Refund ID:</b> {approval.execution.provider_refund_id ?? 'Not confirmed'}</p>}
            <small className="fl-muted">After case approval, the request is reconciled against PayPal, then a different OWNER/ADMIN must approve it. The recorded approver executes the Sandbox refund. PayPal returns funds to the original funding source; approval alone does not move money. Ambiguous provider outcomes are never retried automatically.</small>
          </>}
        </div>}
      </div>
    </section>
  );

  async function submitDisposition() {
    setBusy(true);
    try {
      await api(`/api/v1/financial-lifecycle/cases/${selected.id}/dispositions`, {
        method: 'POST',
        body: JSON.stringify({
          disposition, quantity: 1,
          estimated_recovery: recovered,
          note: `P&L preview: shipping ${returnShipping}; handling ${handling}; write-off ${writeOff}; repair ${repairCost}`
        })
      });
      onMessage('Disposition instruction recorded; no inventory movement occurred.');
      await refresh();
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : 'Disposition could not be recorded.');
    } finally {
      setBusy(false);
    }
  }
}
