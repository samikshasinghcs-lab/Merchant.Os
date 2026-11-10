
import os, tempfile, importlib
from decimal import Decimal

def test_pact_workflow(monkeypatch):
    import app.config as config
    import app.db as database
    # DB_PATH is imported into db module; redirect for isolated test.
    fd,path=tempfile.mkstemp(suffix=".db"); os.close(fd)
    monkeypatch.setattr(database,"DB_PATH",path)
    database.init()
    from app import merchant_intelligence
    merchant_intelligence.init_v2()
    from app import pact
    pact.init_pact()
    a=pact.create_agreement({
        "title":"Website build","description":"Build responsive website; implement authentication; integrate payments",
        "currency":"USD","total_amount":"1000","freelancer_name":"Alex","customer_name":"Jamie",
        "milestones":[
          {"title":"Frontend","amount":"400","acceptance_criteria":["Responsive UI screenshots","Frontend test results"]},
          {"title":"Backend","amount":"600","acceptance_criteria":["API tests","Payment integration test"]}
        ]})
    assert a["status"]=="DRAFT" and len(a["milestones"])==2
    a=pact.approve_agreement(a["id"],"freelancer","Alex","APPROVE")
    assert a["status"]=="AWAITING_APPROVAL"
    a=pact.approve_agreement(a["id"],"customer","Jamie","APPROVE")
    assert a["status"]=="ACTIVE"
    ch=pact.request_scope_change(a["id"],{"requested_by":"customer","request_text":"Add analytics dashboard and automated email notifications","proposed_amount":"100"})
    assert ch["status"]=="PENDING"
    ch=pact.approve_scope_change(ch["id"],"freelancer","Alex","APPROVE")
    ch=pact.approve_scope_change(ch["id"],"customer","Jamie","APPROVE")
    assert ch["status"]=="APPROVED"
    assert pact.get_agreement(a["id"])["version"]==2
    # Add evidence item to existing schema; evidence is registered, not forged.
    with database.db() as c:
        c.execute("INSERT INTO evidence_items VALUES(?,?,?,?,?,?,?)",("EV-1","ORDER_001","test_results","API test output","local://test","merchant_uploaded","2026-11-09T00:00:00Z"))
    m=pact.get_agreement(a["id"])["milestones"][0]
    report=pact.submit_milestone_evidence(a["id"],m["id"],["EV-1"],"Alex")
    assert report["status"]=="READY_FOR_CUSTOMER_REVIEW"
    a=pact.review_milestone(a["id"],m["id"],"ACCEPT","Jamie")
    assert next(x for x in a["milestones"] if x["id"]==m["id"])["status"]=="ACCEPTED"
    os.unlink(path)
