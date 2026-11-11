import { useMemo, useRef, useState, useCallback } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type GridApi, type GridReadyEvent } from "ag-grid-community";
import { api } from "../lib/api";

ModuleRegistry.registerModules([AllCommunityModule]);

export type Txn = { id: string; customer: string; product: string; amount: number; status: string; created_at: string };
type Intel = {
  anomalies: { id: string; reasons: string[]; score: number }[];
  graph: { hotspots: { product: string; orders: number; problem_rate: number }[] };
  simulation: { would_approve: string[]; would_block: { id: string; why: string }[]; exposure: number };
  audit: { intact: boolean; events: number; head: string };
  interpretation: { source: string; text: string; note?: string };
  executed_on: string;
};
const STATUS_COLOR: Record<string, string> = { captured: "#16a34a", refund_requested: "#d97706", refunded: "#2563eb", disputed: "#dc2626" };

export default function TransactionGrid({ rows, events = [] }: { rows: Txn[]; events?: object[] }) {
  const apiRef = useRef<GridApi | null>(null);
  const [intel, setIntel] = useState<Intel | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [runId, setRunId] = useState("");
  const [q, setQ] = useState("");
  const flags = useMemo(() => new Map((intel?.anomalies ?? []).map(a => [a.id, a])), [intel]);

  const cols = useMemo<ColDef<Txn>[]>(() => [
    { field: "id", headerName: "Txn", width: 150, pinned: "left" },
    { field: "created_at", headerName: "Date", filter: "agDateColumnFilter", sort: "desc", valueFormatter: p => String(p.value).slice(0, 16).replace("T", " ") },
    { field: "customer", filter: "agTextColumnFilter" },
    { field: "product", filter: "agTextColumnFilter" },
    { field: "amount", filter: "agNumberColumnFilter", type: "rightAligned", valueFormatter: p => "$" + Number(p.value).toFixed(2) },
    { field: "status", cellRenderer: (p: { value: string }) => <span style={{ color: STATUS_COLOR[p.value] ?? "#64748b", fontWeight: 600 }}>● {p.value}</span> },
    { headerName: "AI risk", width: 130, sortable: true, valueGetter: p => flags.get(p.data!.id)?.score ?? 0,
      cellRenderer: (p: { value: number }) => p.value ? <span style={{ color: "#dc2626", fontWeight: 700 }}>⚠ {(p.value * 100).toFixed(0)}%</span> : <span>—</span>,
      tooltipValueGetter: p => flags.get(p.data!.id)?.reasons.join("; ") ?? "" },
  ], [flags]);
  const defaultColDef = useMemo<ColDef>(() => ({ sortable: true, filter: true, resizable: true, flex: 1, minWidth: 110 }), []);
  const onReady = useCallback((e: GridReadyEvent) => { apiRef.current = e.api; }, []);

  async function runLocal() {
    setBusy("Analysing…"); setError("");
    try { setIntel(await api<Intel>("/api/intelligence/run", { method: "POST", body: JSON.stringify({ transactions: rows, events }) })); }
    catch (e) { setError(e instanceof Error ? e.message : "Analysis failed"); }
    finally { setBusy(""); }
  }
  async function runOnRender() {
    setBusy("Starting Render task…"); setError(""); setRunId("");
    try {
      const started = await api<{ task_run_id: string; task_token: string }>("/api/intelligence/run-on-render", { method: "POST", body: JSON.stringify({ transactions: rows, events }) });
      setRunId(started.task_run_id);
      for (let i = 0; i < 40; i++) {
        setBusy(`Render task ${started.task_run_id} running…`);
        await new Promise(resolve => setTimeout(resolve, 1500));
        const status = await api<any>(`/api/intelligence/render-status/${encodeURIComponent(started.task_token)}`);
        if (status.results) {
          const facts = Array.isArray(status.results) ? status.results[0] : status.results;
          setIntel({ ...facts, interpretation: status.interpretation, executed_on: "render-workflow" });
          break;
        }
        if (["failed", "canceled", "cancelled"].includes(String(status.status).toLowerCase())) throw new Error(`Render task ${status.status}`);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Render Workflow failed"); }
    finally { setBusy(""); }
  }
  return <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2fr) minmax(280px,1fr)", gap: 16 }}>
    <section>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <input placeholder="Quick filter…" value={q} onChange={e => { setQ(e.target.value); apiRef.current?.setGridOption("quickFilterText", e.target.value); }} />
        <button onClick={runLocal} disabled={!!busy}>Run AI analysis</button>
        <button onClick={runOnRender} disabled={!!busy}>Run on Render Workflow</button>
        <button onClick={() => apiRef.current?.exportDataAsCsv()}>Export CSV</button><span>{busy}</span>
      </div>
      {error && <p role="alert" style={{ color: "#b91c1c" }}>{error}</p>}
      <div style={{ height: 520 }}><AgGridReact<Txn> theme={themeQuartz} rowData={rows} columnDefs={cols} defaultColDef={defaultColDef} onGridReady={onReady}
        rowSelection={{ mode: "multiRow", checkboxes: true, headerCheckbox: true }} pagination paginationPageSize={25} tooltipShowDelay={200} getRowId={p => p.data.id} animateRows /></div>
    </section>
    <aside style={{ border: "1px solid #3334", borderRadius: 12, padding: 14, overflow: "auto", maxHeight: 560 }}>
      <h3 style={{ marginTop: 0 }}>AI interpretation</h3>
      {!intel ? <p>Run analysis to see anomalies, graph hotspots, policy simulation and audit integrity.</p> : <>
        <p style={{ fontSize: 12 }}>Source: <b>{intel.interpretation.source}</b> · Executed on: <b>{intel.executed_on}</b>{intel.interpretation.note && <> · {intel.interpretation.note}</>}</p>
        <p style={{ whiteSpace: "pre-wrap" }}>{intel.interpretation.text}</p>
        <h4>Graph hotspots</h4>{intel.graph.hotspots.length ? intel.graph.hotspots.map(h => <div key={h.product}>{h.product}: {(h.problem_rate * 100).toFixed(0)}% of {h.orders} orders</div>) : <div>None</div>}
        <h4>Policy simulation</h4><div>{intel.simulation.would_approve.length} approvable · {intel.simulation.would_block.length} blocked · exposure ${intel.simulation.exposure}</div>
        <h4>Audit</h4><div>{intel.audit.intact ? "✅ chain intact" : "❌ tamper detected"} · {intel.audit.events} events</div><code>{intel.audit.head.slice(0, 32)}…</code>
      </>}
      {runId && <p style={{ fontSize: 12 }}>Render task run: <code>{runId}</code></p>}
    </aside>
  </div>;
}
