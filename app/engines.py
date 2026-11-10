import re, json, uuid, hashlib
from datetime import datetime, timezone
from .db import db
RULES=[("damaged_packaging",["broken","damaged","crushed","packaging"]),("leakage",["leak","leaking","leaked","half empty","spilled"]),("late_delivery",["late","delayed","delay","shipping"]),("wrong_item",["wrong item","incorrect","different product"]),("quality_issue",["quality","smell","irritation","defective","doesn't work"])]
def classify(text):
 t=re.sub(r"\s+", " ", text.lower())
 scores=[(k,sum(term in t for term in terms)) for k,terms in RULES]
 cat,n=max(scores,key=lambda x:x[1])
 if n==0: cat="other"
 sev="high" if any(w in t for w in ["broken","leak","irritation","wrong item"]) else ("medium" if n else "low")
 return cat,sev
def analyze():
 with db() as c:
  rows=c.execute("SELECT * FROM reviews").fetchall()
  for r in rows:
   cat,sev=classify(r["text"]); c.execute("UPDATE reviews SET category=?,cluster_id=?,severity=? WHERE id=?",(cat,cat,sev,r["id"]))
  return [dict(x) for x in c.execute("SELECT cluster_id,COUNT(*) count,AVG(rating) avg_rating,SUM(severity='high') high_count FROM reviews GROUP BY cluster_id ORDER BY count DESC")]
def cluster_list():
 with db() as c: return [dict(x) for x in c.execute("SELECT cluster_id,COUNT(*) count,AVG(rating) avg_rating,SUM(severity='high') high_count FROM reviews GROUP BY cluster_id ORDER BY count DESC")]
def detail(cid):
 with db() as c:
  rs=[dict(x) for x in c.execute("SELECT * FROM reviews WHERE cluster_id=?",(cid,))]
  os=[dict(x) for x in c.execute("SELECT DISTINCT o.* FROM orders o JOIN reviews r ON r.order_id=o.id WHERE r.cluster_id=?",(cid,))]
 return {"reviews":rs,"orders":os}
def propose(cid):
 out=[]
 with db() as c:
  rs=c.execute("SELECT * FROM reviews WHERE cluster_id=?",(cid,)).fetchall(); seen=set()
  for r in rs:
   o=c.execute("SELECT * FROM orders WHERE id=? AND customer_id=?",(r["order_id"],r["customer_id"])).fetchone()
   if not o or o["id"] in seen or o["payment_status"]!="COMPLETED": continue
   seen.add(o["id"])
   # Do not create a second active proposal for an order when the merchant
   # repeats the same cluster action. Re-propose only after a rejection.
   existing=c.execute("SELECT id FROM refunds WHERE order_id=? AND status IN ('PROPOSED','SIMULATED','PENDING','COMPLETED') LIMIT 1",(o["id"],)).fetchone()
   if existing: continue
   pid=str(uuid.uuid4()); idem=hashlib.sha256(pid.encode()).hexdigest()
   ev=json.dumps({"review_id":r["id"],"review_text":r["text"],"match":"exact order and customer reference","confidence":0.99})
   c.execute("INSERT INTO refunds VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(pid,o["id"],o["capture_id"],o["amount"],o["currency"],r["category"],ev,"PROPOSED",idem,None,None,datetime.now(timezone.utc).isoformat()))
   out.append({"id":pid,"order_id":o["id"],"amount":o["amount"],"currency":o["currency"]})
 return out
def insights():
 with db() as c:
  total=c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
  rows=c.execute("SELECT o.batch,r.category,COUNT(*) complaints FROM reviews r JOIN orders o ON o.id=r.order_id GROUP BY o.batch,r.category ORDER BY complaints DESC LIMIT 8").fetchall()
 return {"total_reviews":total,"findings":[{**dict(x),"share_pct":round(100*x["complaints"]/max(total,1),1)} for x in rows],"caveat":"Correlation is not causation. Verify batch and shipping records before acting."}
def draft_dispute(did):
 with db() as c:
  d=c.execute("SELECT * FROM disputes WHERE id=?",(did,)).fetchone()
  if not d:return None
  o=c.execute("SELECT * FROM orders WHERE id=?",(d["order_id"],)).fetchone()
  ev=json.loads(d["evidence_json"])
 return {"draft":f"Dispute: {d['id']}\nReason: {d['reason']}\nCustomer statement: {d['customer_message']}\nOrder: {o['id']}\nPayment status in merchant records: {o['payment_status']}\nEvidence recorded: {', '.join(ev)}\n\nSuggested response: We have reviewed the records currently available and are investigating the customer's concern. The listed records can be provided where relevant. Please assess the evidence against the dispute reason.","evidence":ev,"warning":"Verify every item and deadline. This draft is not submitted automatically."}
def log(event,actor,entity,detail):
 with db() as c:c.execute("INSERT INTO audit(event,actor,entity,detail,created_at) VALUES(?,?,?,?,?)",(event,actor,entity,json.dumps(detail),datetime.now(timezone.utc).isoformat()))


# Deterministic evidence taxonomy. These are operational prompts, not legal
# conclusions or guarantees that a payment provider will accept the material.
EVIDENCE_REQUIREMENTS = {
    "product_not_received": ["tracking", "delivery_confirmation", "customer_communication"],
    "not_as_described": ["product_listing", "order_details", "customer_communication"],
    "damaged_or_defective": ["product_photos", "quality_inspection", "customer_communication"],
    "duplicate_charge": ["transaction_record", "order_details"],
    "credit_not_processed": ["refund_record", "transaction_record"],
}

def assess_evidence(dispute_id):
    with db() as c:
        d = c.execute("SELECT * FROM disputes WHERE id=?", (dispute_id,)).fetchone()
        if not d:
            return None
        rows = c.execute("SELECT * FROM evidence_items WHERE order_id=? ORDER BY created_at", (d["order_id"],)).fetchall()
        order = c.execute("SELECT id,payment_status,amount,currency,capture_id FROM orders WHERE id=?", (d["order_id"],)).fetchone()
    reason = (d["reason"] or "").lower().replace(" ", "_").replace("-", "_")
    required = next((v for k, v in EVIDENCE_REQUIREMENTS.items() if k in reason or reason in k), ["order_details", "customer_communication"])
    present_types = {r["evidence_type"] for r in rows}
    present = [dict(r) for r in rows]
    covered = [x for x in required if x in present_types]
    missing = [x for x in required if x not in present_types]
    return {
        "dispute_id": dispute_id,
        "order_id": d["order_id"],
        "reason": d["reason"],
        "required_evidence_types": required,
        "present_evidence": present,
        "covered_types": covered,
        "missing_types": missing,
        "coverage_pct": round(100 * len(covered) / len(required)) if required else 100,
        "payment_record": dict(order) if order else None,
        "assessment": "EVIDENCE_GAPS_FOUND" if missing else "REVIEW_EVIDENCE_QUALITY",
        "limitations": "Coverage measures only whether evidence categories were recorded. It does not verify authenticity, prove the underlying facts, predict a dispute outcome, or establish legal sufficiency. A human must inspect every item and provider requirements/deadlines.",
    }

# Checkpoint 4 — deterministic customer resolution recommendations.
RESOLUTION_RULES = {
    "damaged_packaging": ("REPLACE_OR_REFUND_REVIEW", "The customer reports damaged packaging. Inspect product photos and fulfilment records; offer a replacement or refund according to merchant policy."),
    "leakage": ("REFUND_OR_REPLACEMENT_REVIEW", "The customer reports leakage. Check batch/quality records and request relevant photos if missing; consider replacement or refund."),
    "late_delivery": ("DELIVERY_INVESTIGATION", "Check carrier tracking and delivery confirmation first. If the delivery window was missed, communicate the revised status and assess shipping compensation under merchant policy."),
    "wrong_item": ("CORRECT_ITEM_FULFILMENT", "Verify the packed item against the order. Arrange the correct item and provide a return label or refund under merchant policy."),
    "quality_issue": ("QUALITY_INVESTIGATION", "Review product/batch quality records and ask for details needed to investigate. Consider replacement or refund under merchant policy."),
    "other": ("HUMAN_REVIEW", "Review the customer's message and order history, then choose an appropriate resolution under merchant policy."),
}
def resolution_recommendation(review_id):
    with db() as c:
        r = c.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not r: return None
        order = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone() if r["order_id"] else None
        evidence = c.execute("SELECT evidence_type,description,source FROM evidence_items WHERE order_id=?", (r["order_id"],)).fetchall() if r["order_id"] else []
    category = r["category"] or classify(r["text"])[0]
    action, rationale = RESOLUTION_RULES.get(category, RESOLUTION_RULES["other"])
    if not order:
        action, rationale = "MANUAL_ORDER_MATCH", "No exact order link is available. Do not recommend a financial action until a merchant verifies the correct order."
    elif order["payment_status"] != "COMPLETED":
        rationale += " The local order is not marked as a completed capture, so a PayPal refund must not be proposed from this record."
    evidence_types = sorted({x["evidence_type"] for x in evidence})
    if not evidence_types:
        rationale += " No evidence references are currently registered for this order."
    return {"review_id":review_id,"order_id":r["order_id"],"category":category,"severity":r["severity"],"recommended_action":action,"rationale":rationale,"evidence_types":evidence_types,"payment_status":order["payment_status"] if order else None,"financial_action_authorized":False,"confidence":"RULE_BASED_TRIAGE_NOT_OUTCOME_PREDICTION"}

def customer_message_draft(review_id, tone="empathetic"):
    with db() as c:
        r = c.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not r: return None
        order = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone() if r["order_id"] else None
    name = (r["customer_name"] or "there").strip()
    order_ref = r["order_id"] or "your order"
    greeting = f"Hi {name},"
    if tone == "concise":
        draft = f"{greeting}\nWe're sorry about the issue you reported for {order_ref}. We're reviewing the order details and will follow up with the next steps. Thank you for letting us know."
    else:
        draft = f"{greeting}\nThank you for telling us about your experience with {order_ref}. I'm sorry this did not meet your expectations. We're reviewing the details you shared alongside the available order records so we can determine the appropriate next step. We'll update you once that review is complete.\n\nThank you for giving us the opportunity to address this."
    return {"review_id":review_id,"order_id":r["order_id"],"customer_message":draft,"tone":tone,"status":"DRAFT_ONLY","warning":"This is an editable draft. It has not been sent to the customer."}

# Checkpoint 5 — deterministic root-cause and exposure analytics.
def root_cause_analysis():
    """Summarize observed complaint concentrations and clearly bounded exposure.

    Counts are descriptive correlations, not causal attribution. Only refunds
    explicitly marked COMPLETED are counted as realized refund outflow.
    """
    with db() as c:
        total_reviews = c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        category_rows = c.execute("""
            SELECT COALESCE(NULLIF(r.category,''),'unclassified') category,
                   COUNT(*) complaints, COUNT(DISTINCT r.order_id) affected_orders,
                   COUNT(DISTINCT o.batch) affected_batches,
                   AVG(r.rating) average_rating
            FROM reviews r LEFT JOIN orders o ON o.id=r.order_id
            GROUP BY COALESCE(NULLIF(r.category,''),'unclassified')
            ORDER BY complaints DESC, category
        """).fetchall()
        batch_rows = c.execute("""
            SELECT COALESCE(o.batch,'unknown') batch, o.product,
                   COUNT(r.id) complaints, COUNT(DISTINCT r.order_id) affected_orders,
                   AVG(r.rating) average_rating
            FROM orders o JOIN reviews r ON r.order_id=o.id
            GROUP BY o.batch,o.product ORDER BY complaints DESC,batch LIMIT 10
        """).fetchall()
        product_rows = c.execute("""
            SELECT COALESCE(o.product,'unknown') product, COUNT(r.id) complaints,
                   COUNT(DISTINCT r.order_id) affected_orders,
                   AVG(r.rating) average_rating
            FROM orders o JOIN reviews r ON r.order_id=o.id
            GROUP BY o.product ORDER BY complaints DESC,product
        """).fetchall()
        refund = c.execute("SELECT currency, SUM(amount) amount, COUNT(*) count FROM refunds WHERE UPPER(status)='COMPLETED' GROUP BY currency").fetchall()
        open_rows = c.execute("""
            SELECT COUNT(DISTINCT r.order_id) orders, SUM(o.amount) gross_order_value
            FROM reviews r JOIN orders o ON o.id=r.order_id
            WHERE UPPER(COALESCE(r.severity,'')) IN ('HIGH','MEDIUM')
              AND NOT EXISTS (SELECT 1 FROM resolutions x WHERE x.review_id=r.id AND x.status='RESOLVED')
        """).fetchone()
    categories = [dict(x) for x in category_rows]
    for row in categories:
        row['complaint_share_pct'] = round(100 * row['complaints'] / max(total_reviews, 1), 1)
        row['average_rating'] = round(row['average_rating'], 2) if row['average_rating'] is not None else None
    batches = [dict(x) for x in batch_rows]
    products = [dict(x) for x in product_rows]
    for group in (batches, products):
        for row in group:
            row['average_rating'] = round(row['average_rating'], 2) if row['average_rating'] is not None else None
    realized = [dict(x) for x in refund]
    for row in realized:
        row['amount'] = round(row['amount'] or 0, 2)
    return {
        'total_reviews': total_reviews,
        'total_orders': total_orders,
        'category_patterns': categories,
        'batch_patterns': batches,
        'product_patterns': products,
        'realized_refund_outflow': realized,
        'unresolved_complaint_exposure': {
            'affected_orders': open_rows['orders'] or 0,
            'gross_order_value_at_risk': round(open_rows['gross_order_value'] or 0, 2),
            'interpretation': 'Gross value of orders linked to medium/high-severity reviews without a RESOLVED resolution. This is not a predicted loss, refund liability, or savings.'
        },
        'methodology': {
            'approach': 'Deterministic aggregation of recorded reviews, order batch/product fields, resolution states, and completed refund records.',
            'causality': 'Complaint concentration by batch or product is correlation only. It does not establish that the batch or product caused the complaint.',
            'data_quality': 'Results depend on the completeness and correctness of merchant-entered order, batch, category, and resolution data.'
        }
    }
