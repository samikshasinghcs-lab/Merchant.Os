
"""PACT commercial trust workflows: draft agreements, scope changes, milestones and guarded PayPal authorization/capture."""
import json, re, uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from .db import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS agreements(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
 freelancer_name TEXT NOT NULL, customer_name TEXT NOT NULL,
 currency TEXT NOT NULL, total_amount TEXT NOT NULL, status TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, extracted_json TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agreement_milestones(
 id TEXT PRIMARY KEY, agreement_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, amount TEXT NOT NULL,
 currency TEXT NOT NULL, acceptance_criteria_json TEXT NOT NULL,
 status TEXT NOT NULL, evidence_ids_json TEXT NOT NULL DEFAULT '[]', paypal_order_id TEXT,
 verification_json TEXT, paypal_authorization_id TEXT, paypal_capture_id TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(agreement_id) REFERENCES agreements(id)
);
CREATE INDEX IF NOT EXISTS idx_milestones_agreement ON agreement_milestones(agreement_id,sequence_no);
CREATE TABLE IF NOT EXISTS agreement_approvals(
 id TEXT PRIMARY KEY, agreement_id TEXT NOT NULL, version INTEGER NOT NULL,
 party_role TEXT NOT NULL, party_name TEXT NOT NULL, decision TEXT NOT NULL,
 note TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(agreement_id) REFERENCES agreements(id)
);
CREATE TABLE IF NOT EXISTS agreement_versions(
 id TEXT PRIMARY KEY, agreement_id TEXT NOT NULL, version INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL, change_reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scope_change_requests(
 id TEXT PRIMARY KEY, agreement_id TEXT NOT NULL, requested_by TEXT NOT NULL,
 request_text TEXT NOT NULL, classification_json TEXT NOT NULL,
 proposed_amount TEXT, currency TEXT, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(agreement_id) REFERENCES agreements(id)
);
CREATE TABLE IF NOT EXISTS scope_change_approvals(
 id TEXT PRIMARY KEY, change_id TEXT NOT NULL, party_role TEXT NOT NULL,
 party_name TEXT NOT NULL, decision TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(change_id) REFERENCES scope_change_requests(id)
);
CREATE TABLE IF NOT EXISTS milestone_events(
 id TEXT PRIMARY KEY, milestone_id TEXT NOT NULL, event_type TEXT NOT NULL,
 actor TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(milestone_id) REFERENCES agreement_milestones(id)
);
"""

def init_pact():
    with db() as c:
        c.executescript(SCHEMA)
        cols={r["name"] for r in c.execute("PRAGMA table_info(agreement_milestones)").fetchall()}
        if "paypal_order_id" not in cols:
            c.execute("ALTER TABLE agreement_milestones ADD COLUMN paypal_order_id TEXT")

def now(): return datetime.now(timezone.utc).isoformat()

def _json(row):
    return dict(row) if row else None

def _agreement(c, aid):
    r=c.execute("SELECT * FROM agreements WHERE id=?",(aid,)).fetchone()
    if not r: raise ValueError("Agreement not found")
    return r

def extract_agreement(text, currency="USD", total_amount=None, freelancer_name="Freelancer", customer_name="Customer"):
    """Transparent baseline extractor. LLM extraction can replace/augment this; no hidden inference."""
    if not isinstance(text,str) or len(text.strip())<10: raise ValueError("Provide a meaningful agreement description")
    lines=[x.strip(" •-\t") for x in re.split(r"[\n;]+",text) if x.strip()]
    keywords=("build","create","design","develop","implement","deliver","provide","integrate","dashboard","website","authentication","payment","frontend","backend","responsive","documentation","testing")
    candidates=[]
    for line in lines:
        if len(line)>3 and (any(k in line.lower() for k in keywords) or len(lines)<=3):
            clean=re.sub(r"^(i need|i want|please|we need|build|create|develop)\s+", "", line, flags=re.I).strip()
            if clean: candidates.append(clean[:240])
    if not candidates: candidates=[text.strip()[:240]]
    deliverables=[]
    for i,item in enumerate(candidates[:20],1):
        deliverables.append({"title":item[:100],"description":item,"acceptance_criteria":[
            "The parties must define objective completion evidence before approval.",
            "Customer reviews the submitted deliverable and records acceptance or rejection."
        ],"sequence":i})
    ambiguities=[]
    if not re.search(r"\b(by|before|deadline|due)\b",text,re.I): ambiguities.append("No deadline is specified.")
    if not re.search(r"\b(responsive|mobile|desktop|browser|device)\b",text,re.I): ambiguities.append("Platform/device expectations are unclear.")
    if not re.search(r"\b(test|acceptance|criteria|approved|review)\b",text,re.I): ambiguities.append("Objective acceptance criteria need customer/freelancer agreement.")
    if total_amount is None: ambiguities.append("Total budget is not specified.")
    return {"deliverables":deliverables,"ambiguities":ambiguities,"extraction_method":"deterministic_baseline","requires_both_party_review":True,
            "note":"Draft extraction only. Parties must correct deliverables, acceptance criteria, deadlines and allocations before approval."}

def create_agreement(payload):
    title=str(payload.get("title") or "Untitled agreement").strip()[:160]
    description=str(payload.get("description") or "").strip()
    currency=str(payload.get("currency") or "USD").upper()
    try: total=Decimal(str(payload.get("total_amount")))
    except (InvalidOperation,TypeError): raise ValueError("total_amount must be a positive decimal")
    if not total.is_finite() or total<=0: raise ValueError("total_amount must be positive")
    if len(currency)!=3 or not currency.isalpha(): raise ValueError("currency must be a 3-letter code")
    extracted=extract_agreement(description,currency,str(total),str(payload.get("freelancer_name") or "Freelancer"),str(payload.get("customer_name") or "Customer"))
    # Explicit milestones may override baseline extraction.
    supplied=payload.get("milestones")
    if supplied:
        if not isinstance(supplied,list) or not supplied: raise ValueError("milestones must be a non-empty list")
        deliverables=[]
        for i,m in enumerate(supplied,1):
            amount=Decimal(str(m.get("amount","0")))
            if amount<=0: raise ValueError("Each milestone amount must be positive")
            criteria=m.get("acceptance_criteria") or []
            if not isinstance(criteria,list) or not criteria: raise ValueError("Each milestone needs acceptance_criteria")
            deliverables.append({"title":str(m.get("title") or f"Milestone {i}")[:120],"description":str(m.get("description") or "")[:1000],"amount":str(amount.quantize(Decimal("0.01"))),"acceptance_criteria":[str(x)[:500] for x in criteria],"sequence":i})
        if sum(Decimal(x["amount"]) for x in deliverables)!=total.quantize(Decimal("0.01")): raise ValueError("Milestone allocations must sum exactly to total_amount")
        extracted["deliverables"]=deliverables
        extracted["ambiguities"]=[x for x in extracted["ambiguities"] if x!="Total budget is not specified."]
    else:
        # Draft allocation is informational only; do not invent payment splits.
        for d in extracted["deliverables"]: d["amount"]=None
        extracted["ambiguities"].append("Milestone payment allocations are not specified.")
    aid="AGR-"+uuid.uuid4().hex[:12].upper(); ts=now()
    with db() as c:
        c.execute("INSERT INTO agreements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(aid,title,description,str(payload.get("freelancer_name") or "Freelancer"),str(payload.get("customer_name") or "Customer"),currency,str(total.quantize(Decimal("0.01"))),"DRAFT",1,json.dumps(extracted),ts,ts))
        for d in extracted["deliverables"]:
            mid="MIL-"+uuid.uuid4().hex[:12].upper()
            c.execute("INSERT INTO agreement_milestones(id,agreement_id,sequence_no,title,description,amount,currency,acceptance_criteria_json,status,evidence_ids_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (mid,aid,d["sequence"],d["title"],d["description"],d["amount"] or "0.00",currency,json.dumps(d["acceptance_criteria"]),"DRAFT","[]",ts,ts))
        c.execute("INSERT INTO agreement_versions VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,aid,1,json.dumps({"payload":payload,"extracted":extracted}),"Initial draft",ts))
    return get_agreement(aid)

def get_agreement(aid):
    with db() as c:
        a=_agreement(c,aid); ms=c.execute("SELECT * FROM agreement_milestones WHERE agreement_id=? ORDER BY sequence_no",(aid,)).fetchall()
        approvals=c.execute("SELECT * FROM agreement_approvals WHERE agreement_id=? ORDER BY created_at",(aid,)).fetchall()
        versions=c.execute("SELECT version,change_reason,created_at FROM agreement_versions WHERE agreement_id=? ORDER BY version",(aid,)).fetchall()
    out=dict(a); out["extracted"]=json.loads(out.pop("extracted_json")); out["milestones"]=[]
    for m in ms:
        x=dict(m); x["acceptance_criteria"]=json.loads(x.pop("acceptance_criteria_json")); x["evidence_ids"]=json.loads(x.pop("evidence_ids_json")); x["verification"]=json.loads(x["verification_json"]) if x["verification_json"] else None; out["milestones"].append(x)
    out["approvals"]=[dict(x) for x in approvals]; out["versions"]=[dict(x) for x in versions]
    return out

def approve_agreement(aid, role, party_name, decision, note=""):
    role=role.lower(); decision=decision.upper()
    if role not in ("freelancer","customer"): raise ValueError("party_role must be freelancer or customer")
    if decision not in ("APPROVE","REJECT"): raise ValueError("decision must be APPROVE or REJECT")
    ts=now()
    with db() as c:
        a=_agreement(c,aid)
        expected=a["freelancer_name"] if role=="freelancer" else a["customer_name"]
        if party_name.strip().casefold()!=expected.strip().casefold(): raise ValueError("Party name does not match the named agreement party")
        if a["status"] not in ("DRAFT","AWAITING_APPROVAL"): raise ValueError("Agreement is not awaiting approval")
        c.execute("INSERT INTO agreement_approvals VALUES(?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,aid,a["version"],role,party_name,decision,note[:1000],ts))
        if decision=="REJECT": c.execute("UPDATE agreements SET status='REJECTED',updated_at=? WHERE id=?",(ts,aid))
        else:
            rows=c.execute("SELECT party_role,decision FROM agreement_approvals WHERE agreement_id=? AND version=?",(aid,a["version"])).fetchall()
            approved={r["party_role"] for r in rows if r["decision"]=="APPROVE"}
            status="ACTIVE" if approved=={"freelancer","customer"} else "AWAITING_APPROVAL"
            c.execute("UPDATE agreements SET status=?,updated_at=? WHERE id=?",(status,ts,aid))
    return get_agreement(aid)

def request_scope_change(aid,payload):
    text=str(payload.get("request_text") or "").strip()
    if len(text)<5: raise ValueError("request_text is required")
    role=str(payload.get("requested_by") or "").lower()
    if role not in ("freelancer","customer"): raise ValueError("requested_by must be freelancer or customer")
    with db() as c:
        a=_agreement(c,aid)
        if a["status"]!="ACTIVE": raise ValueError("Scope changes require an active, mutually approved agreement")
        ms=c.execute("SELECT title,description FROM agreement_milestones WHERE agreement_id=?",(aid,)).fetchall()
    existing=" ".join((m["title"]+" "+m["description"]) for m in ms).lower()
    words=set(re.findall(r"[a-z0-9]+",text.lower()))
    overlap=sum(1 for w in words if w in set(re.findall(r"[a-z0-9]+",existing)))
    classification="POSSIBLE_SCOPE_CHANGE" if overlap<max(2,len(words)*0.35) else "POSSIBLY_WITHIN_EXISTING_SCOPE"
    classification_data={"classification":classification,"token_overlap_count":overlap,"method":"transparent lexical comparison","human_review_required":True}
    amount=payload.get("proposed_amount")
    if amount is not None:
        try:
            d=Decimal(str(amount))
            if d<0: raise ValueError()
            amount=str(d.quantize(Decimal("0.01")))
        except Exception: raise ValueError("proposed_amount must be a non-negative decimal")
    cid="CHG-"+uuid.uuid4().hex[:12].upper();ts=now()
    with db() as c:
        c.execute("INSERT INTO scope_change_requests VALUES(?,?,?,?,?,?,?,?,?,?)",(cid,aid,role,text,json.dumps(classification_data),amount,a["currency"],"PENDING",ts,ts))
    return get_change(cid)

def get_change(cid):
    with db() as c:
        r=c.execute("SELECT * FROM scope_change_requests WHERE id=?",(cid,)).fetchone()
        if not r: return None
        out=dict(r);out["classification"]=json.loads(out.pop("classification_json"));out["approvals"]=[dict(x) for x in c.execute("SELECT * FROM scope_change_approvals WHERE change_id=?",(cid,)).fetchall()]
        return out

def approve_scope_change(cid,role,party_name,decision,note=""):
    role=role.lower();decision=decision.upper()
    if role not in ("freelancer","customer") or decision not in ("APPROVE","REJECT"): raise ValueError("Invalid role or decision")
    ts=now()
    with db() as c:
        r=c.execute("SELECT * FROM scope_change_requests WHERE id=?",(cid,)).fetchone()
        if not r: raise ValueError("Change request not found")
        a=_agreement(c,r["agreement_id"]);expected=a["freelancer_name"] if role=="freelancer" else a["customer_name"]
        if party_name.strip().casefold()!=expected.strip().casefold(): raise ValueError("Party name does not match agreement")
        if r["status"]!="PENDING": raise ValueError("Change request is no longer pending")
        c.execute("INSERT INTO scope_change_approvals VALUES(?,?,?,?,?,?,?)",(uuid.uuid4().hex,cid,role,party_name,decision,note[:1000],ts))
        if decision=="REJECT": status="REJECTED"
        else:
            approvals=c.execute("SELECT party_role,decision FROM scope_change_approvals WHERE change_id=?",(cid,)).fetchall()
            yes={x["party_role"] for x in approvals if x["decision"]=="APPROVE"}
            status="APPROVED" if yes=={"freelancer","customer"} else "PENDING"
        c.execute("UPDATE scope_change_requests SET status=?,updated_at=? WHERE id=?",(status,ts,cid))
        if status=="APPROVED":
            snap={"agreement_id":a["id"],"change_request":dict(r),"approvals":[dict(x) for x in approvals]}
            version=a["version"]+1
            c.execute("UPDATE agreements SET version=?,updated_at=? WHERE id=?",(version,ts,a["id"]))
            c.execute("INSERT INTO agreement_versions VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,a["id"],version,json.dumps(snap),"Approved scope change "+cid,ts))
    return get_change(cid)

def submit_milestone_evidence(aid,mid,evidence_ids,actor):
    if not isinstance(evidence_ids,list) or not evidence_ids: raise ValueError("At least one evidence ID is required")
    with db() as c:
        a=_agreement(c,aid)
        m=c.execute("SELECT * FROM agreement_milestones WHERE id=? AND agreement_id=?",(mid,aid)).fetchone()
        if not m: raise ValueError("Milestone not found")
        if a["status"]!="ACTIVE": raise ValueError("Milestone evidence requires an active agreement")
        # Evidence must exist and be associated with this agreement's referenced commercial work.
        placeholders=",".join("?" for _ in evidence_ids)
        ev=c.execute(f"SELECT id,evidence_type,description FROM evidence_items WHERE id IN ({placeholders})",evidence_ids).fetchall()
        if len(ev)!=len(set(evidence_ids)): raise ValueError("One or more evidence IDs do not exist")
        criteria=json.loads(m["acceptance_criteria_json"])
        text=" ".join(x["evidence_type"]+" "+x["description"] for x in ev).lower()
        checks=[{"criterion":cr,"evidence_found":any(w in text for w in re.findall(r"[a-z0-9]+",cr.lower()) if len(w)>3),"assessment":"KEYWORD_SUPPORT_ONLY"} for cr in criteria]
        report={"criteria_checks":checks,"coverage_count":sum(x["evidence_found"] for x in checks),"criteria_count":len(checks),"status":"READY_FOR_CUSTOMER_REVIEW","limitation":"Keyword overlap is not proof of completion or authenticity. Customer makes acceptance decision."}
        ts=now()
        c.execute("UPDATE agreement_milestones SET status='SUBMITTED',evidence_ids_json=?,verification_json=?,updated_at=? WHERE id=?",(json.dumps(evidence_ids),json.dumps(report),ts,mid))
        c.execute("INSERT INTO milestone_events VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,mid,"EVIDENCE_SUBMITTED",actor,json.dumps(report),ts))
    return report

def review_milestone(aid,mid,decision,party_name,note=""):
    decision=decision.upper()
    if decision not in ("ACCEPT","REJECT"): raise ValueError("decision must be ACCEPT or REJECT")
    ts=now()
    with db() as c:
        a=_agreement(c,aid)
        if party_name.strip().casefold()!=a["customer_name"].strip().casefold(): raise ValueError("Only the named customer can accept/reject the milestone")
        m=c.execute("SELECT * FROM agreement_milestones WHERE id=? AND agreement_id=?",(mid,aid)).fetchone()
        if not m or m["status"]!="SUBMITTED": raise ValueError("Milestone is not awaiting customer review")
        status="ACCEPTED" if decision=="ACCEPT" else "REJECTED"
        c.execute("UPDATE agreement_milestones SET status=?,updated_at=? WHERE id=?",(status,ts,mid))
        c.execute("INSERT INTO milestone_events VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,mid,"CUSTOMER_"+status,party_name,json.dumps({"note":note[:1000]}),ts))
    return get_agreement(aid)

def reliability_indicators():
    with db() as c:
        rows=c.execute("SELECT status,COUNT(*) n FROM agreement_milestones GROUP BY status").fetchall()
        changes=c.execute("SELECT status,COUNT(*) n FROM scope_change_requests GROUP BY status").fetchall()
        approvals=c.execute("SELECT party_role,AVG((julianday('now')-julianday(created_at))*24) avg_hours,COUNT(*) n FROM agreement_approvals GROUP BY party_role").fetchall()
    counts={r["status"]:r["n"] for r in rows}; ch={r["status"]:r["n"] for r in changes}
    completed=sum(counts.get(x,0) for x in ("ACCEPTED",)); submitted=sum(counts.values())
    return {"freelancer":{"milestones_accepted":completed,"milestones_total":submitted,"acceptance_rate":round(completed/submitted,4) if submitted else None,"note":"Descriptive rate from recorded milestone decisions; not a quality or trust score."},
            "customer":{"scope_changes_approved":ch.get("APPROVED",0),"scope_changes_rejected":ch.get("REJECTED",0),"approval_events":[dict(x) for x in approvals],"note":"Approval activity only; does not imply customer reliability."}}
