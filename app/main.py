import json, uuid, hashlib, os, hmac, time, threading
from decimal import Decimal, InvalidOperation
from contextlib import asynccontextmanager
from datetime import datetime,timezone,date
from pathlib import Path
from fastapi import FastAPI,HTTPException,UploadFile,File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from .db import init,seed,db
from .engines import analyze,cluster_list,detail,propose,insights,draft_dispute,log,assess_evidence, resolution_recommendation, customer_message_draft, root_cause_analysis
from .paypal import refund, create_order as paypal_create_order, capture_order as paypal_capture_order, PayPalError
from .config import DEMO,MAX_REFUND,DAILY_CAP,MODE
from . import merchant_intelligence as mi
from . import evidence_disputes as ed
from . import dispute_intelligence as di
from .paypal import list_disputes as paypal_list_disputes, get_dispute as paypal_get_dispute, provide_dispute_evidence
from .config import CLIENT_ID, CLIENT_SECRET, UPLOAD_DIR
from . import pact
from .refund_risk import risk_for_order
from .refund_ai import explain_refund
from .intelligence import router as intelligence_router
@asynccontextmanager
async def lifespan(app):
    from .release_readiness import readiness_report
    deployment_readiness = readiness_report()
    if not deployment_readiness["ready"]:
        raise RuntimeError("MerchantOS deployment readiness checks failed; inspect GET /ready configuration requirements.")
    init()
    # Never inject sample merchant/customer/payment records into a deployed environment.
    is_production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
    if not is_production:
        seed()
    pact.init_pact()
    identity.init_identity()
    analyze()
    yield

app=FastAPI(title="MerchantOS",version="1.0.0",lifespan=lifespan)
app.include_router(intelligence_router)
static=Path(__file__).parent/"static";app.mount("/static",StaticFiles(directory=static),name="static")
@app.get("/",response_class=HTMLResponse)
def home():return (static/"index.html").read_text()

@app.get("/workspace",response_class=HTMLResponse)
def workspace():return (static/"workspace.html").read_text()
@app.get("/health")
def health():
    # Liveness only: does not imply that dependencies or external integrations are ready.
    return {"status": "ok", "demo_mode": DEMO}


@app.get("/ready")
def readiness():
    from .release_readiness import readiness_report
    report = readiness_report()
    if not report["ready"]:
        return JSONResponse(status_code=503, content=report)
    return report


def _require_sandbox_payments():
    if DEMO:
        raise HTTPException(400, "PayPal checkout is disabled in DEMO_MODE. Set DEMO_MODE=false and configure Sandbox credentials.")
    if MODE != "sandbox":
        raise HTTPException(400, "Checkpoint 2 checkout is restricted to PayPal Sandbox. PAYPAL_MODE must be sandbox.")

@app.post("/api/paypal/orders")
def create_paypal_order(body: dict):
    """Create a real PayPal Sandbox checkout order; customer approves it on PayPal."""
    _require_sandbox_payments()
    try:
        amount = Decimal(str(body.get("amount", "")))
    except (InvalidOperation, ValueError):
        raise HTTPException(400, "amount must be a valid positive decimal")
    currency = str(body.get("currency", "USD")).upper()
    product = str(body.get("product", "MerchantOS test purchase")).strip()[:120]
    customer_name = str(body.get("customer_name", "Sandbox customer")).strip()[:100]
    customer_id = str(body.get("customer_id", "sandbox-customer")).strip()[:100]
    if not amount.is_finite() or amount <= 0 or amount > Decimal("100000"):
        raise HTTPException(400, "amount must be greater than 0 and no more than 100000")
    if len(currency) != 3 or not currency.isalpha():
        raise HTTPException(400, "currency must be a 3-letter ISO currency code")
    local_id = "M" + uuid.uuid4().hex[:20].upper()
    idem = hashlib.sha256(("create:" + local_id).encode()).hexdigest()
    try:
        result = paypal_create_order(float(amount), currency, product, idem)
    except PayPalError as exc:
        log("PAYPAL_ORDER_CREATE_FAILED", "merchant", local_id, {"error": str(exc)})
        raise HTTPException(502, str(exc))
    approval = next((x.get("href") for x in result.get("links", []) if x.get("rel") == "payer-action"), None)
    if not approval:
        approval = next((x.get("href") for x in result.get("links", []) if x.get("rel") == "approve"), None)
    with db() as c:
        c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (local_id, customer_id, customer_name, product, "SANDBOX", float(amount), currency,
                   result.get("id"), None, "CREATED", datetime.now(timezone.utc).isoformat()))
    log("PAYPAL_ORDER_CREATED", "merchant", local_id, {"paypal_order_id": result.get("id"), "amount": str(amount), "currency": currency})
    return {"merchant_order_id": local_id, "paypal_order_id": result.get("id"),
            "status": result.get("status"), "approval_url": approval,
            "instructions": "Open approval_url, sign in with a PayPal Sandbox buyer account, and approve the payment. Then call the capture endpoint."}

@app.post("/api/paypal/orders/{merchant_order_id}/capture")
def capture_paypal_order(merchant_order_id: str):
    """Capture a buyer-approved Sandbox order and persist its actual capture ID."""
    _require_sandbox_payments()
    with db() as c:
        order = c.execute("SELECT * FROM orders WHERE id=?", (merchant_order_id,)).fetchone()
    if not order:
        raise HTTPException(404, "Merchant order not found")
    if order["payment_status"] == "COMPLETED" and order["capture_id"]:
        return {"status": "COMPLETED", "capture_id": order["capture_id"], "message": "Already captured; no second capture attempted."}
    if not order["paypal_order_id"]:
        raise HTTPException(400, "Order has no PayPal order ID")
    idem = hashlib.sha256(("capture:" + order["paypal_order_id"]).encode()).hexdigest()
    try:
        result = paypal_capture_order(order["paypal_order_id"], idem)
    except PayPalError as exc:
        log("PAYPAL_CAPTURE_FAILED", "merchant", merchant_order_id, {"error": str(exc)})
        raise HTTPException(502, str(exc))
    captures = []
    for unit in result.get("purchase_units", []):
        captures.extend(unit.get("payments", {}).get("captures", []))
    captured = next((x for x in captures if x.get("status") == "COMPLETED"), None)
    if not captured:
        status = result.get("status", "UNKNOWN")
        log("PAYPAL_CAPTURE_NOT_COMPLETED", "merchant", merchant_order_id, {"status": status})
        return {"status": status, "paypal": result, "message": "PayPal did not report a completed capture. No completed payment was recorded."}
    capture_amount = captured.get("amount", {})
    if capture_amount.get("currency_code") != order["currency"] or Decimal(capture_amount.get("value", "0")) != Decimal(str(order["amount"])).quantize(Decimal("0.01")):
        log("PAYPAL_CAPTURE_AMOUNT_MISMATCH", "system", merchant_order_id, {"capture": capture_amount})
        raise HTTPException(409, "Captured amount/currency differs from the local order. Manual reconciliation required; refund is blocked.")
    with db() as c:
        c.execute("UPDATE orders SET capture_id=?,payment_status='COMPLETED' WHERE id=? AND payment_status='CREATED'",
                  (captured.get("id"), merchant_order_id))
    log("PAYPAL_CAPTURE_COMPLETED", "merchant", merchant_order_id, {"capture_id": captured.get("id"), "amount": capture_amount})
    return {"status": "COMPLETED", "merchant_order_id": merchant_order_id,
            "paypal_order_id": order["paypal_order_id"], "capture_id": captured.get("id"),
            "amount": capture_amount, "paypal_status": result.get("status")}

# Merchant Intelligence v2 — CSV ingestion, semantic grouping, customer/transaction investigation.
@app.get("/api/reviews/connectors")
def review_connectors():
    return {"available_adapters":[{"id":"generic_csv","name":"Generic review CSV","mode":"file_import","status":"ready"},{"id":"shopify_export_csv","name":"Shopify review export CSV","mode":"file_import","status":"adapter_ready_live_oauth_not_configured"},{"id":"trustpilot_export_csv","name":"Trustpilot export CSV","mode":"file_import","status":"adapter_ready_live_oauth_not_configured"},{"id":"google_reviews_csv","name":"Google reviews CSV export","mode":"file_import","status":"adapter_ready_live_oauth_not_configured"}],"note":"These adapters ingest merchant-authorized exports. Direct live OAuth/API connections are not configured; do not scrape platforms or bypass their terms."}

@app.post("/api/reviews/import/{source}")
async def import_reviews(source: str, file: UploadFile = File(...)):
    allowed={"generic_csv","shopify_export_csv","trustpilot_export_csv","google_reviews_csv"}
    if source not in allowed: raise HTTPException(400,"Unsupported source adapter")
    data=await file.read()
    try: result=mi.import_csv_bytes(data,file.filename or 'reviews.csv',source)
    except ValueError as e: raise HTTPException(400,str(e))
    log("REVIEWS_IMPORTED","merchant",result["import_id"],result)
    return result

@app.get("/api/reviews/imports")
def review_import_history():
    with db() as c: return [dict(x) for x in c.execute("SELECT * FROM review_imports ORDER BY imported_at DESC LIMIT 100")]

@app.post("/api/reviews/semantic-analysis")
def semantic_analysis():
    try: result=mi.analyze_reviews()
    except ImportError as e: raise HTTPException(500,"Install merchant intelligence dependencies: "+str(e))
    log("SEMANTIC_REVIEW_ANALYSIS","system","reviews",{"count":result["review_count"],"method":result["method"]})
    return result

@app.get("/api/reviews/semantic-clusters")
def semantic_clusters():
    with db() as c:
        rows=c.execute("SELECT cluster_id,COUNT(*) count,AVG(sentiment_score) avg_sentiment,MIN(analyzed_at) analyzed_at FROM review_analysis_v2 GROUP BY cluster_id ORDER BY count DESC").fetchall()
    return [dict(x) for x in rows]

@app.get("/api/reviews/semantic-clusters/{cluster_id}/explanation")
def semantic_cluster_explanation(cluster_id: str):
    result=mi.explain_cluster(cluster_id)
    if not result: raise HTTPException(404,"Cluster not found. Run semantic analysis first.")
    return result

@app.get("/api/customers")
def customer_list(): return mi.customers()
@app.get("/api/deeptech/lab")
def deeptech_lab():
    from .deeptech_lab import lab_report
    return lab_report()
@app.get("/api/customers/{customer_id}")
def customer_investigation(customer_id: str):
    result=mi.customer_detail(customer_id)
    if not result: raise HTTPException(404,"Customer not found")
    return result

@app.get("/api/transactions/{order_id}")
def transaction_investigation(order_id: str):
    result=mi.transaction_detail(order_id)
    if not result: raise HTTPException(404,"Transaction/order not found")
    return result

@app.post("/api/reviews/{review_id}/match")
def manual_review_match(review_id: str, body: dict):
    order_id=str(body.get("order_id") or "").strip()
    if not order_id: raise HTTPException(400,"order_id required")
    try: result=mi.match_review(review_id,order_id,bool(body.get("confirm",False)))
    except ValueError as e: raise HTTPException(400,str(e))
    log("REVIEW_ORDER_MATCH_RECORDED","merchant",review_id,result)
    return result

@app.get("/api/reviews/{review_id}/match-candidates")
def review_match_candidates(review_id: str):
    with db() as c:
        r=c.execute("SELECT * FROM reviews WHERE id=?",(review_id,)).fetchone()
        if not r: raise HTTPException(404,"Review not found")
        rows=c.execute("SELECT * FROM orders WHERE (? IS NOT NULL AND customer_id=?) OR (? IS NOT NULL AND id=?) ORDER BY created_at DESC LIMIT 50",(r["customer_id"],r["customer_id"],r["order_id"],r["order_id"])).fetchall()
    return [{**dict(o),"suggested_tier":"HIGH" if r["order_id"] and r["order_id"]==o["id"] else "MEDIUM"} for o in rows]

@app.get("/api/dashboard")
def dashboard():
 with db() as c:
  o=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) gross FROM orders").fetchone()
  rv=c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
  dp=c.execute("SELECT COUNT(*) FROM disputes WHERE status='OPEN'").fetchone()[0]
  rf=c.execute("SELECT COUNT(*) FROM refunds WHERE status IN ('SIMULATED','PENDING','COMPLETED')").fetchone()[0]
  pending=c.execute("SELECT COUNT(*) FROM refunds WHERE status='PROPOSED'").fetchone()[0]
  total=c.execute("SELECT COALESCE(SUM(amount),0) FROM refunds WHERE status IN ('SIMULATED','PENDING','COMPLETED')").fetchone()[0]
  rt={r[0]:r[1] for r in c.execute("SELECT currency, COALESCE(SUM(amount),0) FROM refunds WHERE status IN ('SIMULATED','PENDING','COMPLETED') GROUP BY currency")}
  gt={r[0]:r[1] for r in c.execute("SELECT currency, COALESCE(SUM(amount),0) FROM orders GROUP BY currency")}
 return {"orders":o["n"],"gross":o["gross"],"reviews":rv,"disputes":dp,"refund_count":rf,"refund_total":total,"refund_totals":rt,"gross_totals":gt,"pending":pending,"demo":DEMO}
@app.get("/api/clusters")
def clusters():return cluster_list()
@app.get("/api/clusters/{cid}")
def get_cluster(cid):
 d=detail(cid)
 if not d["reviews"]:raise HTTPException(404,"Cluster not found")
 return d
@app.post("/api/analyze")
def reanalyze():
 x=analyze();log("REVIEWS_ANALYZED","system","reviews",{"cluster_count":len(x)});return x
@app.post("/api/refunds/propose")
def create_proposals(body:dict):
 cid=body.get("cluster_id")
 if not cid:raise HTTPException(400,"cluster_id required")
 x=propose(cid);log("REFUNDS_PROPOSED","system",cid,{"count":len(x)})
 return {"proposals":x,"note":"Only exact order+customer matches are proposed. Review evidence before approval."}
@app.get("/api/refunds")
def list_refunds():
    with db() as c:
        rows = c.execute(
            "SELECT * FROM refunds ORDER BY created_at DESC"
        ).fetchall()

    results = []

    for row in rows:
        item = dict(row)
        risk = risk_for_order(item["order_id"])

        item["risk"] = risk
        item["risk_score"] = risk["score"] if risk else None
        item["risk_severity"] = risk["severity"] if risk else "INSUFFICIENT_DATA"
        item["risk_signals"] = risk["signals"] if risk else []
        item["risk_baseline_orders"] = risk["baseline_orders"] if risk else 0

        results.append(item)

    return results
@app.get("/api/refunds/{pid}")
def refund_investigation(pid: str):
    with db() as c:
        row=c.execute("SELECT * FROM refunds WHERE id=?",(pid,)).fetchone()
        if not row: raise HTTPException(404,"Refund not found")
        order=c.execute("SELECT * FROM orders WHERE id=?",(row["order_id"],)).fetchone()
        evidence=c.execute("SELECT * FROM evidence_items WHERE order_id=?",(row["order_id"],)).fetchall()
        audit_rows=c.execute("SELECT * FROM audit WHERE entity=? ORDER BY id DESC LIMIT 30",(pid,)).fetchall()
    return {"refund":dict(row),"order":dict(order) if order else None,"evidence":[dict(x) for x in evidence],"audit":[dict(x) for x in audit_rows]}
@app.get("/api/refunds/{pid}/ai-analysis")
def refund_ai_analysis(pid: str):
    with db() as c:
        row = c.execute(
            "SELECT * FROM refunds WHERE id=?", (pid,)
        ).fetchone()

        if not row: raise HTTPException(404, "Refund not found")

        order = c.execute(
            "SELECT * FROM orders WHERE id=?",
            (row["order_id"],)
        ).fetchone()

        evidence = c.execute(
            "SELECT evidence_type, status FROM evidence_items WHERE order_id=?",
            (row["order_id"],)
        ).fetchall()

        risk = risk_for_order(row["order_id"])

        facts = {
        "refund_amount": float(row["amount"]),
        "currency": row["currency"],
        "refund_status": row["status"],
        "payment_status": order["payment_status"] if order else "UNKNOWN",
        "risk_score": risk["score"] if risk else None,
        "risk_severity": risk["severity"] if risk else "INSUFFICIENT_DATA",
        "risk_signals": risk["signals"] if risk else [],
        "baseline_orders": risk["baseline_orders"] if risk else 0,
        "evidence_count": len(evidence),
        "evidence_types": sorted(set(
            x["evidence_type"] for x in evidence
        )),
        "evidence_statuses": sorted(set(
            x["status"] for x in evidence
        )),
    }

    result = explain_refund(facts)

    return {
        "facts": facts,
        "ai": result,
        "financial_action_authorized": False,
        "human_approval_required": True
    }
@app.post("/api/refunds/{pid}/approve")
def approve(pid, body: dict):
    if body.get("human_approved") is not True:
        raise HTTPException(403, "Explicit human approval required.")

    if body.get("confirmation") != "AUTHORIZE REFUND":
        raise HTTPException(400, "Type AUTHORIZE REFUND to confirm.")

    if not DEMO and MODE != "sandbox":
        raise HTTPException(
            400,
            "Real PayPal refunds are restricted to Sandbox."
        )

    with db() as c:
        p = c.execute(
            "SELECT * FROM refunds WHERE id=?", (pid,)
        ).fetchone()

        if not p:
            raise HTTPException(404, "Proposal not found")

        if p["status"] != "PROPOSED":
            return {
                "status": p["status"],
                "message": "Already processed; no second operation."
            }

        if p["amount"] > MAX_REFUND:
            raise HTTPException(400, "Per-refund cap exceeded")

        used = c.execute(
            """SELECT COALESCE(SUM(amount),0) FROM refunds
            WHERE date(created_at)=?
            AND status IN ('SIMULATED','PENDING','COMPLETED')""",
            (date.today().isoformat(),)
        ).fetchone()[0]

        if used + p["amount"] > DAILY_CAP:
            raise HTTPException(400, "Daily cap exceeded")

        o = c.execute(
            "SELECT * FROM orders WHERE id=?", (p["order_id"],)
        ).fetchone()

        if not o or o["payment_status"] != "COMPLETED":
            raise HTTPException(400, "Payment is not captured")

        prior = c.execute(
            """SELECT COALESCE(SUM(amount),0) FROM refunds
            WHERE order_id=?
            AND status IN ('SIMULATED','PENDING','COMPLETED')""",
            (p["order_id"],)
        ).fetchone()[0]

        if prior + p["amount"] > o["amount"] + 0.001:
            raise HTTPException(400, "Refund exceeds captured amount")

    risk = risk_for_order(p["order_id"])

    log(
        "REFUND_RISK_ASSESSED",
        "system",
        pid,
        risk if risk else {"status": "INSUFFICIENT_DATA"}
    )

    try:
        r = refund(
            p["capture_id"],
            p["amount"],
            p["currency"],
            p["idem"]
        )
    except PayPalError as e:
        log("REFUND_FAILED", "merchant", pid, {"error": str(e)})
        raise HTTPException(502, str(e))

    ps = r.get("status", "UNKNOWN").upper()
    status = (
        "SIMULATED" if ps == "SIMULATED"
        else "COMPLETED" if ps == "COMPLETED"
        else "PENDING"
    )

    with db() as c:
        c.execute(
            """UPDATE refunds
            SET status=?,paypal_id=?,paypal_status=?
            WHERE id=? AND status='PROPOSED'""",
            (status, r.get("id"), ps, pid)
        )

    log(
        "REFUND_RESULT",
        "merchant",
        pid,
        {"status": ps, "paypal_id": r.get("id"), "amount": p["amount"]}
    )

    return {"status": status, "paypal": r, "demo_mode": DEMO}
@app.post("/api/refunds/{pid}/reject")
def reject(pid):
 with db() as c:
  q=c.execute("UPDATE refunds SET status='REJECTED' WHERE id=? AND status='PROPOSED'",(pid,))
  if not q.rowcount:raise HTTPException(404,"Pending proposal not found")
 log("REFUND_REJECTED","merchant",pid,{})
 return {"status":"REJECTED"}
@app.post("/api/evidence")
def add_evidence(body: dict):
    """Register a merchant-supplied evidence reference; files are not uploaded or authenticated here."""
    order_id = str(body.get("order_id", "")).strip()
    evidence_type = str(body.get("evidence_type", "")).strip().lower()
    description = str(body.get("description", "")).strip()
    reference = str(body.get("reference", "")).strip()[:500]
    allowed = {"tracking", "delivery_confirmation", "customer_communication", "product_listing", "order_details", "product_photos", "quality_inspection", "transaction_record", "refund_record", "other"}
    if not order_id or not evidence_type or not description:
        raise HTTPException(400, "order_id, evidence_type and description are required")
    if evidence_type not in allowed:
        raise HTTPException(400, f"evidence_type must be one of: {', '.join(sorted(allowed))}")
    with db() as c:
        if not c.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
            raise HTTPException(404, "Order not found")
        eid = "EV-" + uuid.uuid4().hex[:12].upper()
        created = datetime.now(timezone.utc).isoformat()
        c.execute("INSERT INTO evidence_items VALUES(?,?,?,?,?,?,?)", (eid, order_id, evidence_type, description[:2000], reference or None, "merchant_supplied_unverified", created))
    log("EVIDENCE_REGISTERED", "merchant", eid, {"order_id": order_id, "evidence_type": evidence_type, "source": "merchant_supplied_unverified"})
    return {"id": eid, "order_id": order_id, "evidence_type": evidence_type, "status": "REGISTERED_UNVERIFIED", "created_at": created, "warning": "Merchant-supplied reference only. MerchantOS has not inspected, authenticated, or retained the underlying file."}

@app.get("/api/evidence")
def list_evidence(order_id: str = None):
    with db() as c:
        if order_id:
            rows = c.execute("SELECT * FROM evidence_items WHERE order_id=? ORDER BY created_at DESC", (order_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM evidence_items ORDER BY created_at DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]

# Checkpoint 8 — evidence files, inspection, integrity and real PayPal dispute workflow.
@app.post("/api/evidence/upload")
async def upload_evidence(order_id: str, evidence_type: str, description: str, file: UploadFile = File(...)):
    allowed = {"tracking", "delivery_confirmation", "customer_communication", "product_listing", "order_details", "product_photos", "quality_inspection", "transaction_record", "refund_record", "other"}
    if evidence_type not in allowed: raise HTTPException(400, "Unsupported evidence_type")
    data = await file.read(10 * 1024 * 1024 + 1)
    try: result = ed.store_upload(order_id, evidence_type, description, file.filename or "evidence.bin", data)
    except ValueError as exc: raise HTTPException(400, str(exc))
    log("EVIDENCE_FILE_UPLOADED", "merchant", result["file_id"], {"order_id":order_id,"sha256":result["sha256"],"size_bytes":result["size_bytes"]})
    return result

@app.get("/api/evidence/files")
def evidence_files(order_id: str = None):
    with db() as c:
        sql = "SELECT ef.id file_id,ef.evidence_id,ef.original_name,ef.mime_type,ef.size_bytes,ef.sha256,ef.inspection_json,ef.integrity_status,ef.created_at,ei.order_id,ei.evidence_type FROM evidence_files ef JOIN evidence_items ei ON ei.id=ef.evidence_id"
        rows = c.execute(sql + (" WHERE ei.order_id=?" if order_id else "") + " ORDER BY ef.created_at DESC LIMIT 200", ((order_id,) if order_id else ())).fetchall()
    out=[]
    for row in rows:
        x=dict(row); x["inspection"]=json.loads(x.pop("inspection_json")); out.append(x)
    return out

@app.get("/api/evidence/files/{file_id}/inspect")
def inspect_evidence_file(file_id: str):
    row=ed.evidence_file(file_id)
    if not row: raise HTTPException(404,"Evidence file not found")
    return {"file_id":file_id,"filename":row["original_name"],"mime_type":row["mime_type"],"inspection":json.loads(row["inspection_json"]),"integrity":ed.verify_file(file_id)}

@app.post("/api/evidence/files/{file_id}/verify-integrity")
def verify_evidence_integrity(file_id: str):
    result=ed.verify_file(file_id)
    if not result: raise HTTPException(404,"Evidence file not found")
    log("EVIDENCE_INTEGRITY_CHECKED","system",file_id,result)
    return result

def _require_paypal_disputes():
    if DEMO: raise HTTPException(400,"Real PayPal dispute API is disabled in DEMO_MODE. Set DEMO_MODE=false and configure Sandbox credentials.")
    if MODE != "sandbox": raise HTTPException(400,"This build permits dispute submission only to PayPal Sandbox.")
    if not CLIENT_ID or not CLIENT_SECRET: raise HTTPException(400,"PayPal Sandbox credentials are not configured.")

@app.post("/api/paypal/disputes/sync")
def sync_paypal_disputes(page_size: int = 20):
    _require_paypal_disputes()
    try: result=paypal_list_disputes(max(1,min(page_size,50)))
    except PayPalError as exc: raise HTTPException(502,str(exc))
    items=result.get("items",[])
    now=datetime.now(timezone.utc).isoformat()
    with db() as c:
        for item in items:
            did=item.get("dispute_id")
            if not did: continue
            try: detail=paypal_get_dispute(did)
            except PayPalError: detail=item
            due=detail.get("seller_response_due_date")
            c.execute("INSERT INTO paypal_disputes VALUES(?,?,?,?,?,?,?) ON CONFLICT(dispute_id) DO UPDATE SET status=excluded.status,reason=excluded.reason,lifecycle_stage=excluded.lifecycle_stage,response_due_at=excluded.response_due_at,payload_json=excluded.payload_json,synced_at=excluded.synced_at",(did,detail.get("status"),detail.get("reason"),detail.get("dispute_life_cycle_stage"),due,json.dumps(detail),now))
    log("PAYPAL_DISPUTES_SYNCED","system","paypal",{"count":len(items)})
    return {"synced":len(items),"items":items,"note":"These records came from the configured PayPal Sandbox API."}

@app.get("/api/paypal/disputes")
def list_paypal_disputes_local():
    with db() as c: rows=c.execute("SELECT * FROM paypal_disputes ORDER BY response_due_at ASC").fetchall()
    out=[]
    for row in rows:
        x=dict(row); x["payload"]=json.loads(x.pop("payload_json")); x["deadline_state"]=ed.due_state(x.get("response_due_at")); out.append(x)
    return out

@app.get("/api/paypal/disputes/deadlines")
def paypal_dispute_deadline_monitor():
    """Deterministic response-deadline monitor for locally synced Sandbox disputes."""
    with db() as c:
        rows = c.execute("SELECT dispute_id,status,response_due_at,reason FROM paypal_disputes ORDER BY response_due_at ASC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["deadline"] = di.deadline_summary(item.get("response_due_at"))
        result.append(item)
    return {"count": len(result), "action_required": sum(1 for x in result if x["deadline"]["action_required"]), "items": result}

@app.post("/api/paypal/disputes/{dispute_id}/evidence-readiness")
def paypal_dispute_evidence_readiness(dispute_id: str, body: dict):
    """Preflight evidence package without submitting anything to PayPal."""
    with db() as c:
        dispute_row = c.execute("SELECT * FROM paypal_disputes WHERE dispute_id=?", (dispute_id,)).fetchone()
        if not dispute_row: raise HTTPException(404, "PayPal dispute not synced")
        merchant_order_id = str(body.get("merchant_order_id", "")).strip()
        order = c.execute("SELECT * FROM orders WHERE id=?", (merchant_order_id,)).fetchone() if merchant_order_id else None
        file_ids = body.get("file_ids", [])
        if not isinstance(file_ids, list): raise HTTPException(400, "file_ids must be a list")
        files = []
        integrity = {}
        for fid in file_ids:
            row = c.execute("SELECT ef.*,ei.order_id FROM evidence_files ef JOIN evidence_items ei ON ei.id=ef.evidence_id WHERE ef.id=?", (str(fid),)).fetchone()
            if not row: raise HTTPException(404, f"Evidence file not found: {fid}")
            item = dict(row); files.append(item)
            integrity[str(fid)] = ed.verify_file(str(fid)) or {}
        dispute = dict(dispute_row)
        dispute["payload"] = json.loads(dispute.pop("payload_json"))
    return di.evidence_readiness(dispute, files, merchant_order_id or None, dict(order) if order else None, integrity)

@app.get("/api/paypal/disputes/{dispute_id}")
def get_paypal_dispute_local(dispute_id: str):
    with db() as c: row=c.execute("SELECT * FROM paypal_disputes WHERE dispute_id=?",(dispute_id,)).fetchone()
    if not row: raise HTTPException(404,"PayPal dispute not synced")
    x=dict(row); x["payload"]=json.loads(x.pop("payload_json")); x["deadline_state"]=ed.due_state(x.get("response_due_at")); return x

@app.post("/api/paypal/disputes/{dispute_id}/submit-evidence")
def submit_paypal_dispute_evidence(dispute_id: str, body: dict):
    _require_paypal_disputes()
    if body.get("human_approved") is not True or str(body.get("confirmation", "")) != "SUBMIT TO PAYPAL":
        raise HTTPException(400,"Explicit human approval required: set human_approved=true and confirmation='SUBMIT TO PAYPAL'.")
    evidence_type=str(body.get("evidence_type", "")).strip()
    notes=str(body.get("notes", ""))[:2000]
    file_ids=body.get("file_ids",[])
    if not evidence_type or not isinstance(file_ids,list) or not file_ids: raise HTTPException(400,"evidence_type and at least one file_id are required")
    with db() as c: row=c.execute("SELECT * FROM paypal_disputes WHERE dispute_id=?",(dispute_id,)).fetchone()
    if not row: raise HTTPException(404,"Sync the PayPal dispute before submission")
    payload=json.loads(row["payload_json"]); status=(payload.get("status") or "").upper()
    if status != "WAITING_FOR_SELLER_RESPONSE": raise HTTPException(409,"PayPal dispute is not in WAITING_FOR_SELLER_RESPONSE; submission is blocked")
    requested=[e for e in payload.get("evidences",[]) if e.get("source")=="REQUESTED_FROM_SELLER"]
    if not requested: raise HTTPException(409,"PayPal has not returned a requested-from-seller evidence item; refresh the dispute and inspect its current actions")
    if evidence_type not in {e.get("evidence_type") for e in requested}: raise HTTPException(400,"Evidence type is not among PayPal's requested evidence types")
    rows=[]; paths=[]
    with db() as c:
        merchant_order_id=str(body.get("merchant_order_id", "")).strip()
    if not merchant_order_id or body.get("confirm_order_link") is not True:
        raise HTTPException(400,"Manually link this dispute to a MerchantOS order: provide merchant_order_id and confirm_order_link=true.")
    with db() as c:
        order=c.execute("SELECT * FROM orders WHERE id=?",(merchant_order_id,)).fetchone()
    if not order: raise HTTPException(404,"Merchant order not found")
    # Where PayPal provides transaction identifiers, require an exact provider-to-local match.
    tx_ids=set()
    for tx in payload.get("disputed_transactions",[]) or []:
        for key in ("transaction_id","seller_transaction_id","buyer_transaction_id"):
            if tx.get(key): tx_ids.add(str(tx[key]))
    tx_info=payload.get("transaction_info") or {}
    for key in ("transaction_id","paypal_reference_id"):
        if tx_info.get(key): tx_ids.add(str(tx_info[key]))
    if tx_ids and not ({str(order["capture_id"] or ""),str(order["paypal_order_id"] or "")} & tx_ids):
        raise HTTPException(409,"Selected MerchantOS order does not match PayPal dispute transaction identifiers")
    total_bytes=0
    with db() as c:
        for fid in file_ids:
            f=c.execute("SELECT ef.*,ei.order_id FROM evidence_files ef JOIN evidence_items ei ON ei.id=ef.evidence_id WHERE ef.id=?",(str(fid),)).fetchone()
            if not f: raise HTTPException(404,f"Evidence file not found: {fid}")
            if f["order_id"] != merchant_order_id: raise HTTPException(409,"Every submitted evidence file must belong to the selected merchant order")
            if f["mime_type"] not in {"application/pdf","image/jpeg","image/png","image/gif"}: raise HTTPException(400,"PayPal accepts PDF, JPG/JPEG, GIF and PNG evidence files only")
            if int(f["size_bytes"]) >= 10*1024*1024: raise HTTPException(400,"Each PayPal evidence file must be smaller than 10 MB")
            total_bytes += int(f["size_bytes"])
            verified=ed.verify_file(str(fid))
            if not verified or verified.get("integrity")!="HASH_MATCH": raise HTTPException(409,f"Evidence integrity check failed for {fid}")
            path=(Path(UPLOAD_DIR).resolve()/f["stored_name"]).resolve()
            if Path(UPLOAD_DIR).resolve() not in path.parents: raise HTTPException(400,"Invalid evidence storage path")
            rows.append(dict(f)); paths.append(str(path))
    if total_bytes > 50*1024*1024: raise HTTPException(400,"Total evidence size exceeds PayPal's 50 MB per-request limit")
    links=payload.get("links",[])
    if not any(l.get("rel") in {"provide-evidence","provide_evidence"} for l in links): raise HTTPException(409,"PayPal HATEOAS response does not advertise evidence submission")
    evidence_info=body.get("evidence_info") or {}
    if not isinstance(evidence_info,dict): raise HTTPException(400,"evidence_info must be a JSON object")
    sid="DS-"+uuid.uuid4().hex[:12].upper(); approved_at=datetime.now(timezone.utc).isoformat()
    with db() as c:
        existing=c.execute("SELECT * FROM dispute_submissions WHERE dispute_id=? AND evidence_type=? AND evidence_file_ids_json=? AND status IN ('SUBMITTING','SUBMITTED','UNKNOWN') ORDER BY created_at DESC LIMIT 1",(dispute_id,evidence_type,json.dumps(file_ids))).fetchone()
        if existing: raise HTTPException(409,"This exact evidence package has already been submitted or is in progress; duplicate submission blocked.")
        c.execute("INSERT INTO dispute_submissions VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,dispute_id,json.dumps(file_ids),evidence_type,notes,"merchant",approved_at,None,"SUBMITTING",approved_at))
    log("PAYPAL_DISPUTE_EVIDENCE_APPROVED","merchant",sid,{"dispute_id":dispute_id,"file_ids":file_ids,"evidence_type":evidence_type})
    try: result=provide_dispute_evidence(dispute_id,evidence_type,notes,paths,evidence_info)
    except PayPalError as exc:
        # A timeout/network error or provider 5xx may occur after PayPal accepted the POST.
        # Preserve UNKNOWN and block a blind duplicate submission until manually reconciled.
        uncertain = exc.status_code is None or int(exc.status_code) >= 500
        final_status = "UNKNOWN" if uncertain else "FAILED"
        with db() as c: c.execute("UPDATE dispute_submissions SET status=?,paypal_response_json=? WHERE id=?",(final_status,json.dumps({"error":str(exc),"provider_status_code":exc.status_code,"manual_reconciliation_required":uncertain}),sid))
        log("PAYPAL_DISPUTE_EVIDENCE_UNKNOWN" if uncertain else "PAYPAL_DISPUTE_EVIDENCE_FAILED","system",sid,{"error":str(exc),"manual_reconciliation_required":uncertain})
        raise HTTPException(502, "PayPal submission outcome is unknown; refresh the dispute and reconcile before any retry." if uncertain else str(exc))
    with db() as c: c.execute("UPDATE dispute_submissions SET status='SUBMITTED',paypal_response_json=? WHERE id=?",(json.dumps(result),sid))
    log("PAYPAL_DISPUTE_EVIDENCE_SUBMITTED","merchant",sid,{"dispute_id":dispute_id,"paypal_response":result})
    return {"submission_id":sid,"status":"SUBMITTED_TO_PAYPAL","paypal_response":result,"warning":"Submission acknowledgement is not a dispute outcome. Refresh the dispute to verify its current state."}

@app.get("/api/disputes")
def disputes():
 with db() as c:rows=c.execute("SELECT * FROM disputes").fetchall()
 return [{**dict(x),"evidence":json.loads(x["evidence_json"])} for x in rows]
@app.get("/api/disputes/{did}/assessment")
def dispute_assessment(did):
    result = assess_evidence(did)
    if not result:
        raise HTTPException(404, "Dispute not found")
    return result

@app.post("/api/disputes/{did}/draft")
def dispute_draft(did):
 x=draft_dispute(did)
 if not x:raise HTTPException(404,"Dispute not found")
 log("DISPUTE_DRAFTED","system",did,{"evidence_count":len(x["evidence"])})
 return x
@app.get("/api/insights")
def get_insights():return insights()
@app.get("/api/audit")
def audit():
 with db() as c:rows=c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100").fetchall()
 return [dict(x) for x in rows]


# Checkpoint 4 — Customer Resolution Intelligence
@app.get("/api/resolutions/recommendation/{review_id}")
def get_resolution_recommendation(review_id: str):
    result = resolution_recommendation(review_id)
    if not result:
        raise HTTPException(404, "Review not found")
    return result

@app.get("/api/resolutions/message/{review_id}")
def get_customer_message_draft(review_id: str, tone: str = "empathetic"):
    if tone not in {"empathetic", "concise"}:
        raise HTTPException(400, "tone must be empathetic or concise")
    result = customer_message_draft(review_id, tone)
    if not result:
        raise HTTPException(404, "Review not found")
    return result

@app.post("/api/resolutions")
def create_resolution(body: dict):
    review_id = str(body.get("review_id", "")).strip()
    if not review_id:
        raise HTTPException(400, "review_id required")
    recommendation = resolution_recommendation(review_id)
    draft = customer_message_draft(review_id, str(body.get("tone", "empathetic")))
    if not recommendation or not draft:
        raise HTTPException(404, "Review not found")
    if not recommendation.get("order_id"):
        raise HTTPException(409, "Review has no exact order reference; manual matching is required")
    rid = "RS-" + uuid.uuid4().hex[:12].upper()
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        active = c.execute("SELECT id,status FROM resolutions WHERE review_id=? AND status NOT IN ('RESOLVED','ESCALATED')", (review_id,)).fetchone()
        if active:
            return {"id":active["id"],"status":active["status"],"message":"An active resolution already exists for this review."}
        c.execute("INSERT INTO resolutions VALUES(?,?,?,?,?,?,?,?,?,?)", (rid, review_id, recommendation["order_id"], "OPEN", recommendation["recommended_action"], recommendation["rationale"], draft["customer_message"], None, now, now))
    log("RESOLUTION_CREATED", "merchant", rid, {"review_id":review_id,"order_id":recommendation["order_id"],"recommendation":recommendation["recommended_action"]})
    return {"id":rid,"review_id":review_id,"order_id":recommendation["order_id"],"status":"OPEN","recommendation":recommendation,"customer_message":draft["customer_message"],"warning":"Draft only. No customer message was sent and no financial action was authorized."}

@app.get("/api/resolutions")
def list_resolutions(status: str = None):
    with db() as c:
        if status:
            rows = c.execute("SELECT * FROM resolutions WHERE status=? ORDER BY updated_at DESC", (status.upper(),)).fetchall()
        else:
            rows = c.execute("SELECT * FROM resolutions ORDER BY updated_at DESC LIMIT 200").fetchall()
    return [dict(x) for x in rows]

@app.patch("/api/resolutions/{resolution_id}")
def update_resolution(resolution_id: str, body: dict):
    allowed = {"OPEN", "CONTACTED", "RESOLVED", "ESCALATED"}
    status = str(body.get("status", "")).upper()
    if status not in allowed:
        raise HTTPException(400, f"status must be one of: {', '.join(sorted(allowed))}")
    note = str(body.get("merchant_note", "")).strip()[:2000] or None
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        row = c.execute("SELECT * FROM resolutions WHERE id=?", (resolution_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Resolution not found")
        if row["status"] in {"RESOLVED", "ESCALATED"} and status != row["status"]:
            raise HTTPException(409, "Terminal resolution cannot be reopened; create a new resolution instead")
        c.execute("UPDATE resolutions SET status=?,merchant_note=COALESCE(?,merchant_note),updated_at=? WHERE id=?", (status,note,now,resolution_id))
    log("RESOLUTION_STATUS_CHANGED", "merchant", resolution_id, {"from":row["status"],"to":status,"merchant_note":note})
    return {"id":resolution_id,"status":status,"updated_at":now}


# Checkpoint 5 — root-cause and predictive intelligence (descriptive MVP).
@app.get("/api/root-cause")
def get_root_cause_analysis():
    return root_cause_analysis()


# Checkpoint 6 — Trust, Accountability & Intelligence command centre.
@app.get("/api/accountability")
def accountability_dashboard():
    """Return explainable operational indicators; never fabricate a composite trust score."""
    with db() as c:
        resolutions = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM resolutions GROUP BY status").fetchall()}
        evidence = c.execute("SELECT COUNT(*) total, COUNT(DISTINCT order_id) orders_covered FROM evidence_items").fetchone()
        disputes = c.execute("SELECT COUNT(*) total, SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) open_count FROM disputes").fetchone()
        audit = c.execute("SELECT COUNT(*) total FROM audit").fetchone()["total"]
        refund_rows = c.execute("SELECT currency, status, COUNT(*) n, COALESCE(SUM(amount),0) amount FROM refunds GROUP BY currency,status ORDER BY currency,status").fetchall()
        payment_rows = c.execute("SELECT payment_status, COUNT(*) n FROM orders GROUP BY payment_status").fetchall()
        recent = c.execute("SELECT event, actor, entity, created_at FROM audit ORDER BY id DESC LIMIT 10").fetchall()
    refunds_by_currency = {}
    for row in refund_rows:
        refunds_by_currency.setdefault(row["currency"], {})[row["status"]] = {"count": row["n"], "amount": round(float(row["amount"]), 2)}
    payment_status = {r["payment_status"]: r["n"] for r in payment_rows}
    total_disputes = int(disputes["total"] or 0)
    evidence_orders = int(evidence["orders_covered"] or 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operational_indicators": {
            "resolution_cases": sum(resolutions.values()),
            "resolution_status_counts": resolutions,
            "open_disputes": int(disputes["open_count"] or 0),
            "total_disputes": total_disputes,
            "evidence_items_registered": int(evidence["total"] or 0),
            "orders_with_registered_evidence": evidence_orders,
            "audit_events_recorded": int(audit),
            "payment_status_counts": payment_status,
        },
        "refunds_by_currency_and_status": refunds_by_currency,
        "recent_audit_events": [dict(r) for r in recent],
        "trust_methodology": {
            "composite_score": None,
            "reason": "No composite trust score is calculated. Indicators remain separately observable and explainable.",
            "evidence_caveat": "Registered evidence is merchant-supplied and unverified; registration does not establish authenticity or dispute merit.",
            "financial_caveat": "Refund totals are grouped by currency and status; currencies are never added together.",
            "causality_caveat": "Operational correlations do not establish causation.",
        },
    }


# PACT: agreement, scope-change, milestone and authorization/capture workflows.
from .paypal import create_authorization_order, authorize_order, capture_authorization

@app.post("/api/pact/agreements")
def pact_create_agreement(body: dict):
    try: return pact.create_agreement(body)
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.get("/api/pact/agreements")
def pact_list_agreements():
    with db() as c:
        ids=[r["id"] for r in c.execute("SELECT id FROM agreements ORDER BY created_at DESC").fetchall()]
    return [pact.get_agreement(x) for x in ids]

@app.get("/api/pact/agreements/{agreement_id}")
def pact_get_agreement(agreement_id: str):
    try: return pact.get_agreement(agreement_id)
    except ValueError as exc: raise HTTPException(404,str(exc))

@app.post("/api/pact/agreements/{agreement_id}/approve")
def pact_approve_agreement(agreement_id: str, body: dict):
    try:
        result=pact.approve_agreement(agreement_id,str(body.get("party_role","")),str(body.get("party_name","")),str(body.get("decision","")),str(body.get("note","")))
        log("AGREEMENT_PARTY_DECISION",str(body.get("party_role","")),agreement_id,{"decision":body.get("decision"),"status":result["status"]})
        return result
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.get("/api/pact/agreements/{agreement_id}/versions")
def pact_versions(agreement_id: str):
    try: return pact.get_agreement(agreement_id)["versions"]
    except ValueError as exc: raise HTTPException(404,str(exc))

@app.post("/api/pact/agreements/{agreement_id}/scope-changes")
def pact_scope_change(agreement_id: str, body: dict):
    try:
        result=pact.request_scope_change(agreement_id,body)
        log("SCOPE_CHANGE_REQUESTED",str(body.get("requested_by","")),result["id"],result["classification"])
        return result
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.post("/api/pact/scope-changes/{change_id}/approve")
def pact_scope_change_approve(change_id: str, body: dict):
    try:
        result=pact.approve_scope_change(change_id,str(body.get("party_role","")),str(body.get("party_name","")),str(body.get("decision","")),str(body.get("note","")))
        log("SCOPE_CHANGE_DECISION",str(body.get("party_role","")),change_id,{"decision":body.get("decision"),"status":result["status"]})
        return result
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.post("/api/pact/agreements/{agreement_id}/milestones/{milestone_id}/evidence")
def pact_milestone_evidence(agreement_id: str, milestone_id: str, body: dict):
    try:
        result=pact.submit_milestone_evidence(agreement_id,milestone_id,body.get("evidence_ids",[]),str(body.get("actor","freelancer")))
        log("MILESTONE_EVIDENCE_SUBMITTED",str(body.get("actor","freelancer")),milestone_id,result)
        return result
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.post("/api/pact/agreements/{agreement_id}/milestones/{milestone_id}/review")
def pact_milestone_review(agreement_id: str, milestone_id: str, body: dict):
    try:
        result=pact.review_milestone(agreement_id,milestone_id,str(body.get("decision","")),str(body.get("party_name","")),str(body.get("note","")))
        log("MILESTONE_CUSTOMER_REVIEW",str(body.get("party_name","")),milestone_id,{"status":next(x["status"] for x in result["milestones"] if x["id"]==milestone_id)})
        return result
    except ValueError as exc: raise HTTPException(400,str(exc))

def _pact_sandbox_guard():
    if DEMO or MODE!="sandbox":
        raise HTTPException(400,"PACT payment coordination requires DEMO_MODE=false and PAYPAL_MODE=sandbox. No live payments are supported by this workflow.")

@app.post("/api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/authorize-order")
def pact_authorize_order(agreement_id: str, milestone_id: str):
    _pact_sandbox_guard()
    with db() as c:
        a=c.execute("SELECT * FROM agreements WHERE id=?",(agreement_id,)).fetchone()
        m=c.execute("SELECT * FROM agreement_milestones WHERE id=? AND agreement_id=?",(milestone_id,agreement_id)).fetchone()
    if not a or not m: raise HTTPException(404,"Agreement or milestone not found")
    if a["status"]!="ACTIVE": raise HTTPException(409,"Both parties must approve the agreement first")
    if m["status"] not in ("DRAFT","REJECTED"): raise HTTPException(409,"Milestone is not eligible to create a payment authorization")
    if Decimal(str(m["amount"]))<=0: raise HTTPException(400,"Milestone needs an explicit positive amount allocation")
    import hashlib
    idem=hashlib.sha256(("pact-auth-order:"+milestone_id).encode()).hexdigest()
    try: result=create_authorization_order(float(m["amount"]),m["currency"],m["title"],idem)
    except PayPalError as exc: raise HTTPException(502,str(exc))
    approval=next((x.get("href") for x in result.get("links",[]) if x.get("rel") in ("payer-action","approve")),None)
    with db() as c: c.execute("UPDATE agreement_milestones SET paypal_order_id=?,status='AUTHORIZATION_ORDER_CREATED',updated_at=? WHERE id=?",(result.get("id"),datetime.now(timezone.utc).isoformat(),milestone_id))
    log("PACT_AUTHORIZATION_ORDER_CREATED","merchant",milestone_id,{"paypal_order_id":result.get("id")})
    return {"paypal_order_id":result.get("id"),"status":result.get("status"),"approval_url":approval,"note":"Buyer approval is required. This is an authorization flow, not escrow."}

@app.post("/api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/authorize")
def pact_authorize_payment(agreement_id: str, milestone_id: str):
    _pact_sandbox_guard()
    with db() as c: m=c.execute("SELECT * FROM agreement_milestones WHERE id=? AND agreement_id=?",(milestone_id,agreement_id)).fetchone()
    if not m or not m["paypal_order_id"]: raise HTTPException(409,"Create and approve a PayPal authorization order first")
    if m["status"]!="AUTHORIZATION_ORDER_CREATED": raise HTTPException(409,"Milestone is not awaiting authorization")
    import hashlib
    idem=hashlib.sha256(("pact-authorize:"+m["paypal_order_id"]).encode()).hexdigest()
    try: result=authorize_order(m["paypal_order_id"],idem)
    except PayPalError as exc: raise HTTPException(502,str(exc))
    auth=None
    for unit in result.get("purchase_units",[]):
        auth=unit.get("payments",{}).get("authorizations",[None])[0]
        if auth: break
    if not auth: return {"status":result.get("status"),"paypal":result,"message":"No authorization ID returned; no capture can be attempted."}
    with db() as c: c.execute("UPDATE agreement_milestones SET paypal_authorization_id=?,status='AUTHORIZED',updated_at=? WHERE id=?",(auth["id"],datetime.now(timezone.utc).isoformat(),milestone_id))
    log("PACT_PAYMENT_AUTHORIZED","system",milestone_id,{"authorization_id":auth["id"],"status":auth.get("status")})
    return {"authorization_id":auth["id"],"status":auth.get("status"),"note":"Authorization is a temporary hold, not escrow. Capture remains gated on customer milestone acceptance."}

@app.post("/api/pact/agreements/{agreement_id}/milestones/{milestone_id}/payment/capture")
def pact_capture_milestone(agreement_id: str, milestone_id: str, body: dict):
    _pact_sandbox_guard()
    with db() as c:
        a=c.execute("SELECT * FROM agreements WHERE id=?",(agreement_id,)).fetchone()
        m=c.execute("SELECT * FROM agreement_milestones WHERE id=? AND agreement_id=?",(milestone_id,agreement_id)).fetchone()
    if not a or not m: raise HTTPException(404,"Agreement or milestone not found")
    if m["status"]!="ACCEPTED": raise HTTPException(409,"Customer must accept the milestone before capture")
    if not m["paypal_authorization_id"]: raise HTTPException(409,"No PayPal authorization exists")
    import hashlib
    idem=hashlib.sha256(("pact-capture:"+m["paypal_authorization_id"]).encode()).hexdigest()
    try: result=capture_authorization(m["paypal_authorization_id"],float(m["amount"]),m["currency"],idem)
    except PayPalError as exc: raise HTTPException(502,str(exc))
    capture=None
    for item in result.get("purchase_units",[]):
        capture=item.get("payments",{}).get("captures",[None])[0]
        if capture: break
    if capture and capture.get("status")=="COMPLETED":
        with db() as c:
            c.execute("UPDATE agreement_milestones SET paypal_capture_id=?,status='PAID',updated_at=? WHERE id=? AND status='ACCEPTED'",(capture.get("id"),datetime.now(timezone.utc).isoformat(),milestone_id))
        log("PACT_MILESTONE_CAPTURE_COMPLETED","paypal",milestone_id,{"capture_id":capture.get("id"),"status":capture.get("status")})
    return {"paypal_status":result.get("status"),"capture":capture,"local_status":"PAID" if capture and capture.get("status")=="COMPLETED" else "ACCEPTED","note":"Local paid state is recorded only when PayPal reports a COMPLETED capture."}

@app.get("/api/pact/indicators")
def pact_indicators():
    return pact.reliability_indicators()

# v1.0 identity and workspace access foundation (SQLAlchemy + JWT + RBAC).
from . import auth as identity
from sqlalchemy import select, func
from fastapi import Depends, Request

@app.post('/api/auth/register')
def auth_register(body: dict, request: Request, session=Depends(identity.db_session)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503,'Install requirements.txt to enable SQLAlchemy identity service')
    # First-owner bootstrap is closed by default. An operator must provision a one-time
    # high-entropy token out of band; never let the first internet visitor claim ownership.
    bootstrap = os.getenv('MERCHANTOS_BOOTSTRAP_REGISTRATION_TOKEN', '')
    supplied = request.headers.get('X-MerchantOS-Bootstrap-Token', '')
    if len(bootstrap) < 32 or not hmac.compare_digest(bootstrap.encode("utf-8"), supplied.encode("utf-8")):
        raise HTTPException(403, 'Initial registration is disabled; use the operator-provisioned bootstrap credential.')
    if session.scalar(select(func.count(identity.Tenant.id))) > 0:
        raise HTTPException(409,'This release is configured for a single-merchant pilot. Multi-merchant domain isolation must be completed before additional workspaces are enabled.')
    if not str(body.get('name','')).strip() or not str(body.get('tenant_name','')).strip(): raise HTTPException(400,'Name and business name are required')
    user, member=identity.register_user(session, str(body.get('name','')).strip(), str(body.get('email','')), str(body.get('password','')), str(body.get('tenant_name','')).strip())
    return {'access_token':identity.make_token(user,member),'token_type':'bearer','user':{'id':user.id,'email':user.email,'name':user.name,'tenant_id':member.tenant_id,'tenant_name':member.tenant.name,'role':member.role}}

@app.post('/api/auth/login')
def auth_login(body: dict, session=Depends(identity.db_session)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503,'Install requirements.txt to enable SQLAlchemy identity service')
    user,member=identity.login_user(session,str(body.get('email','')),str(body.get('password','')))
    return {'access_token':identity.make_token(user,member),'token_type':'bearer','user':{'id':user.id,'email':user.email,'name':user.name,'tenant_id':member.tenant_id,'tenant_name':member.tenant.name,'role':member.role}}

@app.get('/api/auth/me')
def auth_me(principal=Depends(identity.current_principal)): return principal

@app.get('/api/v1/workspace')
def workspace_profile(principal=Depends(identity.current_principal)): return principal

@app.get('/api/v1/workspace/members')
def workspace_members(principal=Depends(identity.require_roles('OWNER','ADMIN')), session=Depends(identity.db_session)):
    rows=session.execute(select(identity.Membership,identity.User).join(identity.User,identity.User.id==identity.Membership.user_id).where(identity.Membership.tenant_id==principal['tenant_id'])).all()
    return [{'user_id':u.id,'email':u.email,'name':u.name,'role':m.role} for m,u in rows]

@app.post('/api/v1/workspace/members/{user_id}/role')
def workspace_change_role(user_id: str, body: dict, principal=Depends(identity.require_roles('OWNER','ADMIN')), session=Depends(identity.db_session)):
    role=str(body.get('role','')).upper()
    if role not in {'ADMIN','ANALYST','OPERATOR','VIEWER'}: raise HTTPException(400,'Unsupported role')
    member=session.scalar(select(identity.Membership).where(identity.Membership.tenant_id==principal['tenant_id'],identity.Membership.user_id==user_id))
    if not member: raise HTTPException(404,'Workspace member not found')
    if member.role=='OWNER': raise HTTPException(403,'Owner role cannot be reassigned')
    member.role=role; session.commit(); return {'user_id':user_id,'role':role}

@app.get('/api/transactions')
def transaction_list():
    with db() as c: return [dict(x) for x in c.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 250')]


# Defense-in-depth HTTP boundary. Authentication is enforced before route handlers;
# webhook routes rely on PayPal signature verification and internal callbacks on HMAC.
_AUTH_LIMITS = {}
_AUTH_LIMIT_LOCK = threading.Lock()
_AUTH_WINDOW_SECONDS = 60
_AUTH_MAX_ATTEMPTS = 8

@app.middleware('http')
async def security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
    response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
    response.headers.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
    response.headers.setdefault('Cache-Control', 'no-store' if request.url.path.startswith('/api/') else 'no-cache')
    response.headers.setdefault('Pragma', 'no-cache' if request.url.path.startswith('/api/') else 'public')
    if request.url.scheme == 'https':
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response

@app.middleware('http')
async def api_access_control(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    # Do not expose legacy shared-SQLite business handlers in multi-tenant mode.
    # Only the PostgreSQL tenant-domain router and explicitly scoped event/auth
    # endpoints remain reachable until every legacy repository is migrated.
    from .tenant_guard import legacy_route_blocked
    if legacy_route_blocked(path, os.getenv('MULTI_TENANT_ENABLED', 'false').lower() == 'true'):
        return JSONResponse(status_code=503, content={
            'detail': 'This legacy endpoint is disabled in multi-tenant mode until tenant-scoped migration is complete.',
            'code': 'LEGACY_ROUTE_NOT_TENANT_SAFE',
        })
    # Cheap early body cap; upload handlers additionally enforce content and file limits.
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            limit = 12 * 1024 * 1024 if path.endswith('/upload') or '/import/' in path else 2 * 1024 * 1024
            if int(content_length) > limit:
                return JSONResponse(status_code=413, content={'detail': 'Request body exceeds the configured limit'})
        except ValueError:
            return JSONResponse(status_code=400, content={'detail': 'Invalid Content-Length'})

    # Process-local throttling is a defense-in-depth fallback, not a distributed rate limiter.
    if path in {'/api/auth/login', '/api/auth/register'} and method == 'POST':
        host = request.client.host if request.client else 'unknown'
        key = (path, host)
        now = time.monotonic()
        with _AUTH_LIMIT_LOCK:
            attempts = [stamp for stamp in _AUTH_LIMITS.get(key, []) if now - stamp < _AUTH_WINDOW_SECONDS]
            if len(attempts) >= _AUTH_MAX_ATTEMPTS:
                return JSONResponse(status_code=429, content={'detail': 'Too many authentication attempts; try again later'}, headers={'Retry-After': str(_AUTH_WINDOW_SECONDS)})
            attempts.append(now); _AUTH_LIMITS[key] = attempts

    externally_authenticated = (
        path == '/api/paypal/webhooks/receive'
        or path == '/api/paypal/webhooks/verify'
        or path.startswith('/api/paypal/webhooks/tenant/')
        or path in {'/api/internal/paypal-events', '/api/internal/tenant-paypal-events/process'}
    )
    if os.getenv('AUTH_REQUIRED', 'false').lower() == 'true' and path.startswith('/api/') and path not in {'/api/auth/login', '/api/auth/register'} and not externally_authenticated:
        if not identity.AUTH_AVAILABLE:
            return JSONResponse(status_code=503, content={'detail': 'Identity service dependencies are not installed'})
        header = request.headers.get('authorization', '')
        if not header.lower().startswith('bearer '):
            return JSONResponse(status_code=401, content={'detail': 'Authentication required'})
        try:
            claims = identity.jwt.decode(header.split(' ', 1)[1], identity.SECRET,
                algorithms=[identity.ALGORITHM], issuer=identity.JWT_ISSUER, audience=identity.JWT_AUDIENCE,
                options={'require_exp': True, 'require_iat': True, 'require_nbf': True, 'require_sub': True, 'require_jti': True})
            with identity.SessionLocal() as session:
                user = session.get(identity.User, claims.get('sub'))
                member = session.scalar(select(identity.Membership).where(identity.Membership.user_id == claims.get('sub'), identity.Membership.tenant_id == claims.get('tenant_id')))
                if not user or not user.is_active or not member:
                    raise ValueError('inactive membership')
                role = member.role
                if method in {'POST', 'PUT', 'PATCH', 'DELETE'} and role not in {'OWNER', 'ADMIN', 'OPERATOR'}:
                    return JSONResponse(status_code=403, content={'detail': 'This workspace role cannot perform write operations'})
                sensitive = any(x in path for x in ('/approve', '/capture', '/authorize', '/submit-evidence', '/payment/', '/invoices/', '/vault/', '/refund-approvals', '/paypal/credentials'))
                if sensitive and role not in {'OWNER', 'ADMIN'}:
                    return JSONResponse(status_code=403, content={'detail': 'This operation requires OWNER or ADMIN authorization'})
                if path.endswith('/role') and role != 'OWNER':
                    return JSONResponse(status_code=403, content={'detail': 'Only the workspace OWNER can change member roles'})
        except Exception:
            return JSONResponse(status_code=401, content={'detail': 'Invalid or expired access token'})
    return await call_next(request)

# v1.2 tenant-scoped PostgreSQL endpoints. Legacy SQLite routes remain single-workspace
# and registration stays restricted until every legacy route has been migrated.
from .tenant_api import router as tenant_domain_router
app.include_router(tenant_domain_router)

@app.post('/api/paypal/webhooks/verify')
def verify_paypal_webhook(body: dict, request: Request):
    """Verification utility for webhook receivers; never accepts an unverified event as trusted."""
    import os
    from .paypal_security import verify_webhook_signature
    webhook_id=os.getenv('PAYPAL_WEBHOOK_ID','')
    if not webhook_id or not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(503,'PayPal webhook verification is not configured')
    event=body.get('event') if isinstance(body.get('event'),dict) else body
    if not isinstance(event,dict): raise HTTPException(400,'Expected event object')
    ok=verify_webhook_signature(dict(request.headers),event,webhook_id,CLIENT_ID,CLIENT_SECRET,MODE)
    if not ok: raise HTTPException(401,'PayPal webhook signature verification failed')
    return {'verified':True,'event_type':event.get('event_type'),'event_id':event.get('id'),'instruction':'Verified event only. Apply idempotent event processing before changing payment state.'}


@app.post('/api/paypal/webhooks/receive')
async def receive_paypal_webhook(body: dict, request: Request):
    """Verify a PayPal webhook, then enqueue a sanitized event in Render Workflows.

    This endpoint does not mutate payment state. It only stores event-processing metadata.
    """
    import os, json
    from datetime import datetime, timezone
    from .paypal_security import verify_webhook_signature

    webhook_id = os.getenv('PAYPAL_WEBHOOK_ID', '')
    if not webhook_id or not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(503, 'PayPal webhook verification is not configured')
    # PayPal sends the event as the root JSON object. The wrapper form is also
    # accepted for compatibility with the existing /verify helper.
    event = body.get('event') if isinstance(body.get('event'), dict) else body
    if not isinstance(event, dict):
        raise HTTPException(400, 'Expected event object')
    if not verify_webhook_signature(dict(request.headers), event, webhook_id, CLIENT_ID, CLIENT_SECRET, MODE):
        raise HTTPException(401, 'PayPal webhook signature verification failed')
    from .workflow_events import sanitize_paypal_event
    try:
        safe_event = sanitize_paypal_event(event)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    event_id = safe_event['event_id']
    event_type = safe_event['event_type']
    with db() as c:
        existing = c.execute('SELECT status, workflow_run_id FROM paypal_webhook_events WHERE event_id=?', (event_id,)).fetchone()
        if existing and existing['status'] in {'QUEUED', 'RECONCILIATION_REQUIRED', 'IGNORED_UNSUPPORTED'}:
            return {'accepted': True, 'duplicate': True, 'status': existing['status'], 'workflow_run_id': existing['workflow_run_id']}
        if existing:
            c.execute("UPDATE paypal_webhook_events SET status='RECEIVED', workflow_run_id=NULL, summary_json=?, received_at=?, processed_at=NULL WHERE event_id=?", (json.dumps(safe_event), datetime.now(timezone.utc).isoformat(), event_id))
        else:
            c.execute('INSERT INTO paypal_webhook_events(event_id,event_type,resource_id,status,workflow_run_id,summary_json,received_at,processed_at) VALUES(?,?,?,?,?,?,?,NULL)',
                      (event_id, event_type, safe_event['resource_id'], 'RECEIVED', None, json.dumps(safe_event), datetime.now(timezone.utc).isoformat()))

    workflow_slug = os.getenv('WORKFLOW_SERVICE_SLUG', '').strip()
    if not workflow_slug or not os.getenv('RENDER_API_KEY'):
        raise HTTPException(503, 'Render Workflows is not configured; verified event retained for safe retry')
    try:
        from render import RenderAsync
        client = RenderAsync()
        run = await client.workflows.start_task(
            f"{workflow_slug}/process_paypal_event",
            {'event': safe_event},
        )
    except Exception as exc:
        log('PAYPAL_WEBHOOK_WORKFLOW_DISPATCH_FAILED', 'system', event_id, {'error': type(exc).__name__})
        raise HTTPException(502, 'Verified event could not be queued in Render Workflows')
    with db() as c:
        c.execute("UPDATE paypal_webhook_events SET status=CASE WHEN status='PROCESSED' THEN status ELSE 'QUEUED' END, workflow_run_id=? WHERE event_id=?", (str(run.id), event_id))
    log('PAYPAL_WEBHOOK_QUEUED', 'system', event_id, {'event_type': event_type, 'workflow_run_id': str(run.id)})
    return {'accepted': True, 'duplicate': False, 'status': str(run.status), 'workflow_run_id': str(run.id), 'event_id': event_id}


@app.post('/api/paypal/webhooks/tenant/{endpoint_token}')
async def receive_tenant_paypal_webhook(endpoint_token: str, request: Request):
    """Public PayPal webhook endpoint with opaque tenant routing and provider signature check.

    The URL token locates one merchant configuration; it does not authenticate the
    event. PayPal's transmission signature is verified against that tenant's webhook ID.
    Only an allowlisted, sanitized envelope is persisted.
    """
    import json, os
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(413, 'PayPal webhook payload exceeds the 1 MB limit')
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'Webhook body must be valid JSON')
    if not isinstance(event, dict):
        raise HTTPException(400, 'Expected PayPal event object')
    from .tenant_operations import resolve_paypal_webhook_route, receive_verified_webhook, record_webhook_workflow_run
    route = resolve_paypal_webhook_route(endpoint_token)
    if not route:
        raise HTTPException(404, 'Webhook endpoint is not active')
    try:
        result = receive_verified_webhook(route['tenant_id'], dict(request.headers), event, route['environment'])
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        log('TENANT_PAYPAL_WEBHOOK_PERSIST_FAILED', 'system', 'webhook', {'error_class': 'PersistenceError'})
        raise HTTPException(503, 'Verified event could not be persisted; PayPal may retry delivery')

    if not result.get('duplicate') and os.getenv('RENDER_API_KEY') and os.getenv('WORKFLOW_SERVICE_SLUG'):
        try:
            from render import RenderAsync
            client = RenderAsync()
            run = await client.workflows.start_task(
                f"{os.getenv('WORKFLOW_SERVICE_SLUG').strip()}/process_tenant_paypal_event",
                {'tenant_id': route['tenant_id'], 'event_id': result['event_id']},
            )
            record_webhook_workflow_run(route['tenant_id'], result['event_id'], str(run.id))
            result['workflow_dispatch'] = 'QUEUED'
            result['workflow_run_id'] = str(run.id)
            result['workflow_status'] = str(run.status)
        except Exception as exc:
            # The durable inbox remains RECEIVED. An authenticated operator can process
            # or replay it; provider delivery is acknowledged only after DB persistence.
            log('TENANT_PAYPAL_WORKFLOW_DISPATCH_FAILED', 'system', result.get('event_id', 'unknown'),
                {'error_class': type(exc).__name__})
            result['workflow_dispatch'] = 'PENDING_LOCAL_QUEUE'
            result['workflow_dispatch_error'] = 'Render dispatch unavailable; event remains in durable inbox.'
    result['financial_write_authorized'] = False
    return JSONResponse(status_code=202 if not result.get('duplicate') else 200, content=result)


@app.post('/api/internal/tenant-paypal-events/process')
def process_tenant_paypal_event_callback(body: dict, request: Request):
    """Private Render Workflow callback. Shared secret + tenant/event lookup are mandatory."""
    import os, hmac
    expected = os.getenv('MERCHANTOS_WORKFLOW_SHARED_SECRET', '')
    supplied = request.headers.get('X-MerchantOS-Workflow-Secret', '')
    if len(expected) < 32 or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, 'Invalid workflow callback credential')
    tenant_id = str(body.get('tenant_id') or '').strip()
    event_id = str(body.get('event_id') or '').strip()
    if not tenant_id or len(tenant_id) > 36 or not event_id or len(event_id) > 200:
        raise HTTPException(400, 'tenant_id and event_id are required')
    from .event_processor import process_event_once
    try:
        result = process_event_once(tenant_id, event_id, force_due=True)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    if result.get('status') in {'RETRY_WAIT', 'BUSY'}:
        raise HTTPException(503, 'Event processing requires a retry')
    return {**result, 'financial_write_authorized': False}


@app.post('/api/internal/paypal-events')
def record_workflow_paypal_event(body: dict, request: Request):
    """Private callback used by the Render task; shared-secret protected and idempotent."""
    import os, hmac
    from datetime import datetime, timezone
    expected = os.getenv('MERCHANTOS_WORKFLOW_SHARED_SECRET', '')
    supplied = request.headers.get('X-MerchantOS-Workflow-Secret', '')
    if len(expected) < 32 or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, 'Invalid workflow callback credential')
    event = body.get('event')
    if not isinstance(event, dict) or not event.get('event_id') or not event.get('event_type'):
        raise HTTPException(400, 'Invalid sanitized event')
    event_id = str(event['event_id']).strip()
    if len(event_id) > 128 or not str(event.get('event_type', '')).strip():
        raise HTTPException(400, 'Invalid event identity')
    from .workflow_engine import build_reconciliation_work_item
    try:
        work_item = build_reconciliation_work_item(event)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with db() as c:
        row = c.execute('SELECT status FROM paypal_webhook_events WHERE event_id=?', (event_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Verified webhook event was not registered')
        if row['status'] in {'RECONCILIATION_REQUIRED', 'IGNORED_UNSUPPORTED'}:
            return {'recorded': True, 'duplicate': True, 'event_id': event_id, 'status': row['status'], 'work_item': work_item}
        c.execute("UPDATE paypal_webhook_events SET status=?, processed_at=? WHERE event_id=?", (work_item['status'], datetime.now(timezone.utc).isoformat(), event_id))
    log('PAYPAL_WEBHOOK_RECONCILIATION_QUEUED' if work_item['requires_provider_reconciliation'] else 'PAYPAL_WEBHOOK_QUARANTINED', 'system', event_id, {'event_type': str(event['event_type']), 'domain': work_item['domain'], 'action': work_item['action'], 'workflow_run_id': body.get('workflow_run_id'), 'financial_write_authorized': False})
    return {'recorded': True, 'duplicate': False, 'event_id': event_id, 'status': work_item['status'], 'work_item': work_item}


@app.get('/api/paypal/webhooks/events')
def list_paypal_webhook_events():
    with db() as c:
        rows = c.execute('SELECT event_id,event_type,resource_id,status,workflow_run_id,received_at,processed_at FROM paypal_webhook_events ORDER BY received_at DESC LIMIT 100').fetchall()
    return [dict(row) for row in rows]

# v1.3 tenant administration and security operations.
from .operations_api import router as operations_router
app.include_router(operations_router)

# Phase 1: expanded PayPal financial operations. These routes remain Sandbox-only.
from .paypal import (
    create_invoice_draft as paypal_create_invoice_draft,
    get_invoice as paypal_get_invoice,
    send_invoice as paypal_send_invoice,
    search_transactions as paypal_search_transactions,
    create_vault_setup_token as paypal_create_vault_setup_token,
    get_vault_setup_token as paypal_get_vault_setup_token,
    create_vault_payment_token as paypal_create_vault_payment_token,
)
from .config import PUBLIC_APP_URL
from datetime import timedelta
import re


def _require_paypal_financial_api():
    if DEMO:
        raise HTTPException(400, "PayPal financial APIs are disabled in DEMO_MODE. Configure Sandbox credentials and DEMO_MODE=false.")
    if MODE != "sandbox":
        raise HTTPException(400, "MerchantOS Phase 1 financial API routes are restricted to PayPal Sandbox.")
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(503, "PayPal Sandbox credentials are not configured.")


@app.get("/api/paypal/capabilities")
def paypal_capabilities():
    """Machine-readable integration inventory; configuration is not a claim of live connectivity."""
    return {
        "environment": MODE,
        "demo_mode": DEMO,
        "configured": bool(CLIENT_ID and CLIENT_SECRET),
        "integrations": {
            "orders_v2": {"status": "implemented", "operations": ["create", "capture"]},
            "payments_v2": {"status": "implemented", "operations": ["capture_refund", "authorization_capture"]},
            "disputes_v1": {"status": "implemented", "operations": ["list", "show", "provide_evidence"]},
            "invoicing_v2": {"status": "implemented", "operations": ["create_draft", "show", "send_with_human_approval"]},
            "transaction_search_v1": {"status": "implemented", "operations": ["list_transactions"]},
            "vault_v3": {"status": "implemented", "operations": ["create_setup_token", "finalize_approved_setup_token"]},
            "webhooks": {"status": "verification_utility_only", "operations": ["verify_signature"]},
        },
        "safety": ["sandbox_only", "no_card_pan_or_cvv_storage", "invoice_send_requires_human_confirmation", "vault_token_finalization_requires_payer_approval"],
    }


@app.post("/api/paypal/invoices")
def create_paypal_invoice(body: dict):
    """Create a PayPal draft invoice. Draft creation does not notify the customer."""
    _require_paypal_financial_api()
    invoice = body.get("invoice")
    if not isinstance(invoice, dict):
        raise HTTPException(400, "invoice must be an object matching PayPal Invoicing v2")
    detail = invoice.get("detail") or {}
    items = invoice.get("items") or []
    if not isinstance(detail, dict) or not isinstance(items, list) or not items:
        raise HTTPException(400, "invoice.detail and a non-empty invoice.items array are required")
    currency = str(detail.get("currency_code", "")).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(400, "invoice.detail.currency_code must be a 3-letter ISO currency code")
    idem = "mos-inv-create-" + uuid.uuid4().hex
    try:
        result = paypal_create_invoice_draft(invoice, idem)
    except PayPalError as exc:
        log("PAYPAL_INVOICE_CREATE_FAILED", "merchant", "invoice", {"error": str(exc)})
        raise HTTPException(502, str(exc))
    log("PAYPAL_INVOICE_DRAFT_CREATED", "merchant", result.get("id", "unknown"),
        {"status": result.get("status"), "currency": currency, "item_count": len(items)})
    return {"invoice_id": result.get("id"), "status": result.get("status"),
            "href": next((x.get("href") for x in result.get("links", []) if x.get("rel") == "self"), None),
            "paypal": result}


@app.get("/api/paypal/invoices/{invoice_id}")
def show_paypal_invoice(invoice_id: str):
    _require_paypal_financial_api()
    if not re.fullmatch(r"[A-Za-z0-9-]{3,80}", invoice_id):
        raise HTTPException(400, "Invalid PayPal invoice ID")
    try:
        result = paypal_get_invoice(invoice_id)
    except PayPalError as exc:
        raise HTTPException(502, str(exc))
    return result


@app.post("/api/paypal/invoices/{invoice_id}/send")
def send_paypal_invoice(invoice_id: str, body: dict):
    """Sending an invoice notifies a payer; explicit merchant approval is mandatory."""
    _require_paypal_financial_api()
    if body.get("human_approved") is not True or body.get("confirmation") != "SEND INVOICE TO CUSTOMER":
        raise HTTPException(400, "Explicit merchant approval required: human_approved=true and confirmation='SEND INVOICE TO CUSTOMER'.")
    if not re.fullmatch(r"[A-Za-z0-9-]{3,80}", invoice_id):
        raise HTTPException(400, "Invalid PayPal invoice ID")
    idem = "mos-inv-send-" + hashlib.sha256(invoice_id.encode()).hexdigest()[:40]
    try:
        result = paypal_send_invoice(invoice_id, idem, send_to_recipient=True, send_to_invoicer=True)
    except PayPalError as exc:
        log("PAYPAL_INVOICE_SEND_FAILED", "merchant", invoice_id, {"error": str(exc)})
        raise HTTPException(502, str(exc))
    log("PAYPAL_INVOICE_SENT", "merchant", invoice_id, {"status": result.get("status", "ACKNOWLEDGED")})
    return {"invoice_id": invoice_id, "status": "SEND_REQUEST_ACCEPTED", "paypal": result,
            "note": "PayPal accepted the send request. Retrieve the invoice to verify its resulting status."}


@app.get("/api/paypal/transactions")
def search_paypal_transactions(start_date: str, end_date: str, page_size: int = 50,
                               page: int = 1, transaction_id: str | None = None,
                               transaction_status: str | None = None,
                               transaction_currency: str | None = None):
    """Search PayPal reporting transactions. PayPal reporting may lag by up to three hours."""
    _require_paypal_financial_api()
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "start_date and end_date must be RFC3339 timestamps with timezone and seconds")
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise HTTPException(400, "Date range must be timezone-aware and end_date must be after start_date")
    if end - start > timedelta(days=31):
        raise HTTPException(400, "PayPal Transaction Search supports a maximum 31-day date range")
    if not 1 <= page_size <= 100 or page < 1:
        raise HTTPException(400, "page_size must be 1–100 and page must be >= 1")
    if transaction_status and transaction_status not in {"D", "P", "S", "V"}:
        raise HTTPException(400, "transaction_status must be D, P, S or V")
    if transaction_currency and not re.fullmatch(r"[A-Za-z]{3}", transaction_currency):
        raise HTTPException(400, "transaction_currency must be a 3-letter ISO currency code")
    if transaction_id and not re.fullmatch(r"[A-Za-z0-9]{17,19}", transaction_id):
        raise HTTPException(400, "transaction_id must be a 17–19 character PayPal transaction/order ID")
    try:
        result = paypal_search_transactions(start_date=start_date, end_date=end_date,
            page_size=page_size, page=page, transaction_id=transaction_id,
            transaction_status=transaction_status, transaction_currency=transaction_currency)
    except PayPalError as exc:
        raise HTTPException(502, str(exc))
    return {"transactions": result.get("transaction_details", []),
            "total_items": result.get("total_items"), "total_pages": result.get("total_pages"),
            "page": page, "page_size": page_size,
            "reporting_lag_note": "PayPal documents that executed transactions can take up to three hours to appear.",
            "paypal": result}


@app.post("/api/paypal/vault/setup-tokens")
def create_paypal_vault_setup_token(body: dict):
    """Start customer-consented PayPal Wallet vaulting; no card data is accepted or stored."""
    _require_paypal_financial_api()
    customer_id = str(body.get("customer_id", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", customer_id):
        raise HTTPException(400, "customer_id must be 1–22 alphanumeric, underscore or hyphen characters")
    if body.get("customer_consent") is not True:
        raise HTTPException(400, "Customer consent must be explicitly confirmed before creating a setup token")
    try:
        result = paypal_create_vault_setup_token(customer_id,
            PUBLIC_APP_URL + "/paypal/vault/return", PUBLIC_APP_URL + "/paypal/vault/cancel",
            "mos-vault-setup-" + uuid.uuid4().hex)
    except PayPalError as exc:
        raise HTTPException(502, str(exc))
    approval = next((x.get("href") for x in result.get("links", []) if x.get("rel") in {"approve", "payer-action"}), None)
    log("PAYPAL_VAULT_SETUP_CREATED", "merchant", customer_id, {"setup_token_id": result.get("id")})
    return {"setup_token_id": result.get("id"), "status": result.get("status"),
            "approval_url": approval,
            "note": "Customer must complete PayPal's approval flow. MerchantOS does not collect PAN/CVV."}


@app.post("/api/paypal/vault/payment-tokens")
def finalize_paypal_vault_payment_token(body: dict):
    """Convert an approved setup token to a vault payment token after checking PayPal state."""
    _require_paypal_financial_api()
    setup_token_id = str(body.get("setup_token_id", "")).strip()
    customer_id = str(body.get("customer_id", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", setup_token_id):
        raise HTTPException(400, "Invalid setup_token_id")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", customer_id):
        raise HTTPException(400, "Invalid customer_id")
    if body.get("human_approved") is not True or body.get("confirmation") != "FINALIZE CUSTOMER-APPROVED VAULT TOKEN":
        raise HTTPException(400, "Explicit merchant confirmation required to finalize the customer-approved token")
    try:
        setup = paypal_get_vault_setup_token(setup_token_id)
        if str(setup.get("status", "")).upper() not in {"APPROVED", "PAYER_ACTION_COMPLETED"}:
            raise HTTPException(409, "PayPal setup token is not approved; token finalization is blocked")
        result = paypal_create_vault_payment_token(setup_token_id, customer_id,
            "mos-vault-token-" + hashlib.sha256(setup_token_id.encode()).hexdigest()[:40])
    except PayPalError as exc:
        raise HTTPException(502, str(exc))
    # Do not persist payment token data. Only a masked identifier and status enter the audit log.
    token_id = result.get("id")
    log("PAYPAL_VAULT_PAYMENT_TOKEN_CREATED", "merchant", customer_id,
        {"token_id_suffix": str(token_id or "")[-6:], "payment_source_type": next(iter((result.get("payment_source") or {}).keys()), "unknown")})
    return {"created": bool(token_id), "token_id": token_id, "customer": result.get("customer"),
            "payment_source": {"type": next(iter((result.get("payment_source") or {}).keys()), "unknown")},
            "note": "Token identifier returned once; full payment-source details are not persisted by MerchantOS."}


@app.get("/paypal/vault/return", response_class=HTMLResponse)
def paypal_vault_return():
    return "<main><h1>PayPal approval returned</h1><p>Customer approval flow completed. The merchant application must verify the setup token with PayPal and explicitly finalize the vault token. No payment is charged by this return page.</p></main>"

@app.get("/paypal/vault/cancel", response_class=HTMLResponse)
def paypal_vault_cancel():
    return "<main><h1>PayPal vault setup cancelled</h1><p>No payment token was finalized.</p></main>"


# Additive tenant-scoped financial lifecycle workspace.
from .financial_lifecycle import router as financial_lifecycle_router
app.include_router(financial_lifecycle_router)
