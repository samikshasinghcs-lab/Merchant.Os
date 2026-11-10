from app.engines import classify
def test_damaged(): assert classify("Bottle broken, packaging crushed")[0]=="damaged_packaging"
def test_late(): assert classify("Delivery was delayed")[0]=="late_delivery"
def test_other(): assert classify("Wonderful service")[0]=="other"

from fastapi.testclient import TestClient
from app.main import app
from app import db as db_module


def test_backend_vertical_slice(tmp_path, monkeypatch):
    # Isolate every API test from a developer's local database.
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        dashboard = client.get("/api/dashboard").json()
        assert (dashboard["orders"], dashboard["reviews"], dashboard["disputes"]) == (15, 40, 4)

        clusters = client.get("/api/clusters").json()
        assert len(clusters) == 5
        cluster_id = "damaged_packaging"
        detail = client.get(f"/api/clusters/{cluster_id}").json()
        assert len(detail["reviews"]) > 0

        first = client.post("/api/refunds/propose", json={"cluster_id": cluster_id})
        assert first.status_code == 200
        proposals = first.json()["proposals"]
        assert len(proposals) > 0
        # Re-running the same operation must not create duplicate active proposals.
        second = client.post("/api/refunds/propose", json={"cluster_id": cluster_id})
        assert second.status_code == 200
        assert second.json()["proposals"] == []

        proposal_id = proposals[0]["id"]
        approved = client.post(f"/api/refunds/{proposal_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "SIMULATED"
        repeated = client.post(f"/api/refunds/{proposal_id}/approve")
        assert repeated.status_code == 200
        assert repeated.json()["status"] == "SIMULATED"
        assert "Already processed" in repeated.json()["message"]

        disputes = client.get("/api/disputes").json()
        draft = client.post(f"/api/disputes/{disputes[0]['id']}/draft")
        assert draft.status_code == 200
        assert "Evidence recorded" in draft.json()["draft"]
        assert draft.json()["evidence"]

        insight = client.get("/api/insights").json()
        assert insight["total_reviews"] == 40
        assert insight["findings"]
        assert client.get("/api/audit").status_code == 200


def test_refund_cap_and_rejection(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "limits.db"))
    with TestClient(app) as client:
        proposals = client.post("/api/refunds/propose", json={"cluster_id": "damaged_packaging"}).json()["proposals"]
        assert proposals
        pid = proposals[0]["id"]
        monkeypatch.setattr(main_module, "MAX_REFUND", 1.0)
        blocked = client.post(f"/api/refunds/{pid}/approve")
        assert blocked.status_code == 400
        assert "cap" in blocked.json()["detail"].lower()
        monkeypatch.setattr(main_module, "MAX_REFUND", 2000.0)
        rejected = client.post(f"/api/refunds/{pid}/reject")
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"
        # Rejected proposals cannot later be approved.
        again = client.post(f"/api/refunds/{pid}/approve")
        assert again.status_code == 200
        assert again.json()["status"] == "REJECTED"


def test_paypal_checkout_sandbox_vertical_slice(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "paypal.db"))
    monkeypatch.setattr(main_module, "DEMO", False)
    monkeypatch.setattr(main_module, "MODE", "sandbox")

    def fake_create(amount, currency, description, idem):
        assert amount == 12.50 and currency == "USD"
        return {"id": "PAYPAL-ORDER-123", "status": "PAYER_ACTION_REQUIRED",
                "links": [{"rel": "payer-action", "href": "https://sandbox.paypal.test/approve"}]}

    def fake_capture(order_id, idem):
        assert order_id == "PAYPAL-ORDER-123"
        return {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
            {"id": "CAPTURE-REAL-123", "status": "COMPLETED",
             "amount": {"currency_code": "USD", "value": "12.50"}}
        ]}}]}

    monkeypatch.setattr(main_module, "paypal_create_order", fake_create)
    monkeypatch.setattr(main_module, "paypal_capture_order", fake_capture)
    with TestClient(app) as client:
        created = client.post("/api/paypal/orders", json={"amount": "12.50", "currency": "USD",
                                                            "product": "Sandbox test item"})
        assert created.status_code == 200
        data = created.json()
        assert data["paypal_order_id"] == "PAYPAL-ORDER-123"
        assert data["approval_url"].startswith("https://")

        captured = client.post(f"/api/paypal/orders/{data['merchant_order_id']}/capture")
        assert captured.status_code == 200
        assert captured.json()["capture_id"] == "CAPTURE-REAL-123"
        repeated = client.post(f"/api/paypal/orders/{data['merchant_order_id']}/capture")
        assert repeated.status_code == 200
        assert "Already captured" in repeated.json()["message"]

        with db_module.db() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (data["merchant_order_id"],)).fetchone()
            assert row["payment_status"] == "COMPLETED"
            assert row["capture_id"] == "CAPTURE-REAL-123"


def test_paypal_checkout_blocked_in_demo(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "demo-paypal.db"))
    monkeypatch.setattr(main_module, "DEMO", True)
    with TestClient(app) as client:
        response = client.post("/api/paypal/orders", json={"amount": "1.00"})
        assert response.status_code == 400
        assert "DEMO_MODE" in response.json()["detail"]


def test_real_refunds_restricted_to_sandbox(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "live-block.db"))
    monkeypatch.setattr(main_module, "DEMO", False)
    monkeypatch.setattr(main_module, "MODE", "live")
    with TestClient(app) as client:
        response = client.post("/api/refunds/not-a-real-proposal/approve")
        assert response.status_code == 400
        assert "restricted to Sandbox" in response.json()["detail"]


def test_evidence_register_and_deterministic_assessment(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "evidence.db"))
    with TestClient(app) as client:
        disputes = client.get("/api/disputes").json()
        dispute = disputes[0]
        did = dispute["id"]
        before = client.get(f"/api/disputes/{did}/assessment")
        assert before.status_code == 200
        assert before.json()["missing_types"]
        order_id = dispute["order_id"]
        added = client.post("/api/evidence", json={"order_id": order_id,
            "evidence_type": "tracking", "description": "Carrier tracking reference reviewed",
            "reference": "internal://orders/record-1"})
        assert added.status_code == 200
        assert added.json()["status"] == "REGISTERED_UNVERIFIED"
        after = client.get(f"/api/disputes/{did}/assessment").json()
        assert "tracking" in after["covered_types"]
        assert after["coverage_pct"] >= before.json()["coverage_pct"]
        assert "does not verify authenticity" in after["limitations"]
        assert client.get("/api/evidence", params={"order_id": order_id}).json()


def test_evidence_validation_and_order_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "evidence-validation.db"))
    with TestClient(app) as client:
        bad_type = client.post("/api/evidence", json={"order_id": "MISSING", "evidence_type": "magic", "description": "x"})
        assert bad_type.status_code == 400
        missing_order = client.post("/api/evidence", json={"order_id": "MISSING", "evidence_type": "order_details", "description": "x"})
        assert missing_order.status_code == 404
        missing_fields = client.post("/api/evidence", json={})
        assert missing_fields.status_code == 400


def test_customer_resolution_recommendation_message_and_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "resolution.db"))
    with TestClient(app) as client:
        with db_module.db() as conn:
            review = conn.execute("SELECT * FROM reviews WHERE order_id IS NOT NULL LIMIT 1").fetchone()
        assert review
        rid = review["id"]
        rec = client.get(f"/api/resolutions/recommendation/{rid}")
        assert rec.status_code == 200
        assert rec.json()["financial_action_authorized"] is False
        draft = client.get(f"/api/resolutions/message/{rid}")
        assert draft.status_code == 200
        assert draft.json()["status"] == "DRAFT_ONLY"
        created = client.post("/api/resolutions", json={"review_id": rid})
        assert created.status_code == 200
        resolution_id = created.json()["id"]
        assert created.json()["status"] == "OPEN"
        contacted = client.patch(f"/api/resolutions/{resolution_id}", json={"status":"CONTACTED", "merchant_note":"Draft reviewed by merchant"})
        assert contacted.status_code == 200
        resolved = client.patch(f"/api/resolutions/{resolution_id}", json={"status":"RESOLVED"})
        assert resolved.status_code == 200
        reopened = client.patch(f"/api/resolutions/{resolution_id}", json={"status":"OPEN"})
        assert reopened.status_code == 409
        assert client.get("/api/resolutions").json()[0]["status"] == "RESOLVED"


def test_resolution_validation_and_duplicate_active_record(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "resolution-validation.db"))
    with TestClient(app) as client:
        assert client.post("/api/resolutions", json={}).status_code == 400
        assert client.get("/api/resolutions/recommendation/NOPE").status_code == 404
        with db_module.db() as conn:
            review = conn.execute("SELECT id FROM reviews WHERE order_id IS NOT NULL LIMIT 1").fetchone()
        first = client.post("/api/resolutions", json={"review_id":review["id"]}).json()
        second = client.post("/api/resolutions", json={"review_id":review["id"]}).json()
        assert first["id"] == second["id"]
        assert "already exists" in second["message"]


def test_resolution_status_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "resolution-status.db"))
    with TestClient(app) as client:
        assert client.patch("/api/resolutions/missing", json={"status":"MAGIC"}).status_code == 400
        assert client.patch("/api/resolutions/missing", json={"status":"OPEN"}).status_code == 404


def test_root_cause_analysis_is_explicit_about_correlation_and_exposure(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "root-cause.db"))
    with TestClient(app) as client:
        response = client.get("/api/root-cause")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_reviews"] == 40
        assert payload["total_orders"] == 15
        assert payload["category_patterns"]
        assert payload["batch_patterns"]
        assert payload["product_patterns"]
        assert "correlation" in payload["methodology"]["causality"].lower()
        assert "not a predicted loss" in payload["unresolved_complaint_exposure"]["interpretation"]
        assert payload["realized_refund_outflow"] == []


def test_root_cause_counts_only_completed_refunds(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "root-cause-refunds.db"))
    with TestClient(app) as client:
        with db_module.db() as conn:
            conn.execute("INSERT INTO refunds VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                "r-pending", "ORD-001", "CAP-001", 10.0, "USD", "test", "{}", "PENDING", "idem-pending", None, None, "2026-01-01T00:00:00+00:00"))
            conn.execute("INSERT INTO refunds VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                "r-complete", "ORD-002", "CAP-002", 12.5, "USD", "test", "{}", "COMPLETED", "idem-complete", "PAY-1", "COMPLETED", "2026-01-01T00:00:00+00:00"))
        payload = client.get("/api/root-cause").json()
        assert payload["realized_refund_outflow"] == [{"currency":"USD", "amount":12.5, "count":1}]


def test_accountability_endpoint_exposes_explainable_metrics():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.get('/api/accountability')
        assert response.status_code == 200
        payload = response.json()
        assert payload['trust_methodology']['composite_score'] is None
        assert 'refunds_by_currency_and_status' in payload
        assert 'operational_indicators' in payload

def test_merchant_intelligence_v2(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "mi.db"))
    with TestClient(app) as client:
        csv_data = b"review_id,customer_id,order_id,product,rating,review_text\nR-CSV-1,CUST-CSV,ORDER-CSV,Serum,1,The serum bottle leaked and arrived damaged\nR-CSV-2,CUST-CSV,ORDER-CSV,Serum,2,Serum packaging is leaking and broken\n"
        imported = client.post("/api/reviews/import/generic_csv", files={"file": ("reviews.csv", csv_data, "text/csv")})
        assert imported.status_code == 200, imported.text
        assert imported.json()["rows_imported"] == 2
        # Duplicate import is idempotent by review ID.
        again = client.post("/api/reviews/import/generic_csv", files={"file": ("reviews.csv", csv_data, "text/csv")})
        assert again.status_code == 200 and again.json()["duplicates_skipped"] == 2
        analysis = client.post("/api/reviews/semantic-analysis")
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["review_count"] == 42
        assert analysis.json()["method"] in ("tfidf_cosine_fallback",) or "sentence-transformers" in analysis.json()["method"]
        customer = client.get("/api/customers/CUST-CSV")
        assert customer.status_code == 200 and len(customer.json()["reviews"]) == 2
        from app.db import db as open_db
        from datetime import datetime, timezone
        with open_db() as conn:
            conn.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("ORDER-CSV","CUST-CSV","CSV Customer","Serum","BATCH-CSV",499.0,"INR",None,None,"CREATED",datetime.now(timezone.utc).isoformat()))
        tx = client.get("/api/transactions/ORDER-CSV")
        assert tx.status_code == 200 and tx.json()["order"]["id"] == "ORDER-CSV"
        candidates = client.get("/api/reviews/R-CSV-1/match-candidates")
        assert candidates.status_code == 200 and candidates.json()
        match = client.post("/api/reviews/R-CSV-1/match", json={"order_id":"ORDER-CSV", "confirm":True})
        assert match.status_code == 200 and match.json()["tier"] == "HIGH"
        explanation = client.get("/api/reviews/semantic-clusters/SEM-001/explanation")
        assert explanation.status_code == 200
        assert "review_count" in explanation.json()["facts"]


def test_evidence_upload_inspection_and_integrity(tmp_path, monkeypatch):
    import app.evidence_disputes as ed
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "evidence.db"))
    monkeypatch.setattr(ed, "UPLOAD_DIR", str(tmp_path / "uploads"))
    with TestClient(app) as client:
        content = b"Delivery confirmation: parcel delivered on 2026-11-09."
        response = client.post(
            "/api/evidence/upload",
            params={"order_id": "ORD-001", "evidence_type": "delivery_confirmation", "description": "Carrier delivery record"},
            files={"file": ("delivery.txt", content, "text/plain")},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["authenticity"] == "NOT_ESTABLISHED"
        assert payload["inspection"]["text_extraction"] == "plain_text"
        integrity = client.post(f"/api/evidence/files/{payload['file_id']}/verify-integrity")
        assert integrity.status_code == 200
        assert integrity.json()["integrity"] == "HASH_MATCH"
        assert "does not prove" in integrity.json()["meaning"]
        file_row=ed.evidence_file(payload["file_id"])
        (tmp_path / "uploads" / file_row["stored_name"]).write_bytes(b"tampered")
        tampered=client.post(f"/api/evidence/files/{payload['file_id']}/verify-integrity")
        assert tampered.json()["integrity"] == "HASH_MISMATCH"
        assert client.get("/api/evidence/files?order_id=ORD-001").status_code == 200


def test_evidence_upload_rejects_fake_pdf_and_unknown_order(tmp_path, monkeypatch):
    import app.evidence_disputes as ed
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "reject.db"))
    monkeypatch.setattr(ed, "UPLOAD_DIR", str(tmp_path / "uploads"))
    with TestClient(app) as client:
        fake_pdf = client.post("/api/evidence/upload", params={"order_id":"ORD-001","evidence_type":"other","description":"bad"}, files={"file":("fake.pdf",b"not a pdf","application/pdf")})
        assert fake_pdf.status_code == 400
        missing = client.post("/api/evidence/upload", params={"order_id":"NO_SUCH_ORDER","evidence_type":"other","description":"test"}, files={"file":("ok.txt",b"hello","text/plain")})
        assert missing.status_code == 400


def test_paypal_dispute_submit_requires_human_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "disputes.db"))
    with TestClient(app) as client:
        r=client.post("/api/paypal/disputes/PP-D-TEST/submit-evidence",json={"human_approved":False,"confirmation":""})
        assert r.status_code == 400


def test_human_approved_paypal_dispute_submission_is_gated_and_audited(tmp_path, monkeypatch):
    import json
    import app.main as main_module
    import app.evidence_disputes as ed
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "submit.db"))
    monkeypatch.setattr(ed, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(main_module, "DEMO", False)
    monkeypatch.setattr(main_module, "MODE", "sandbox")
    monkeypatch.setattr(main_module, "CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(main_module, "CLIENT_SECRET", "sandbox-secret")
    calls=[]
    monkeypatch.setattr(main_module, "provide_dispute_evidence", lambda did, et, notes, paths, info=None: calls.append((did,et,notes,paths,info)) or {"status":"SUBMITTED","links":[]})
    with TestClient(app) as client:
        upload=client.post("/api/evidence/upload",params={"order_id":"ORD-001","evidence_type":"delivery_confirmation","description":"Proof of delivery"},files={"file":("proof.txt",b"not for PayPal submission","text/plain")})
        assert upload.status_code == 200
        file_id=upload.json()["file_id"]
        # The dispute is synchronized from PayPal; this fixture represents its stored provider response.
        payload={"dispute_id":"PP-D-TEST","status":"WAITING_FOR_SELLER_RESPONSE","reason":"MERCHANDISE_OR_SERVICE_NOT_RECEIVED","evidences":[{"evidence_type":"PROOF_OF_FULFILLMENT","source":"REQUESTED_FROM_SELLER"}],"links":[{"rel":"provide_evidence"}]}
        with db_module.db() as c:
            c.execute("INSERT INTO paypal_disputes VALUES(?,?,?,?,?,?,?)",("PP-D-TEST",payload["status"],payload["reason"],"CHARGEBACK",None,json.dumps(payload),"2026-11-09T00:00:00+00:00"))
        blocked=client.post("/api/paypal/disputes/PP-D-TEST/submit-evidence",json={"human_approved":True,"confirmation":"SUBMIT TO PAYPAL","evidence_type":"PROOF_OF_FULFILLMENT","file_ids":[file_id],"merchant_order_id":"ORD-001","confirm_order_link":True})
        assert blocked.status_code == 400 # TXT is accepted in the vault, but PayPal requires PDF/JPG/GIF/PNG.
        # Create a structurally valid PNG for the PayPal submission path.
        from PIL import Image
        import io
        buffer=io.BytesIO(); Image.new("RGB",(2,2)).save(buffer,format="PNG"); png=buffer.getvalue()
        upload2=client.post("/api/evidence/upload",params={"order_id":"ORD-001","evidence_type":"delivery_confirmation","description":"Proof image"},files={"file":("proof.png",png,"image/png")})
        assert upload2.status_code == 200
        file_id=upload2.json()["file_id"]
        submitted=client.post("/api/paypal/disputes/PP-D-TEST/submit-evidence",json={"human_approved":True,"confirmation":"SUBMIT TO PAYPAL","evidence_type":"PROOF_OF_FULFILLMENT","file_ids":[file_id],"merchant_order_id":"ORD-001","confirm_order_link":True})
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "SUBMITTED_TO_PAYPAL"
        assert len(calls)==1
        duplicate=client.post("/api/paypal/disputes/PP-D-TEST/submit-evidence",json={"human_approved":True,"confirmation":"SUBMIT TO PAYPAL","evidence_type":"PROOF_OF_FULFILLMENT","file_ids":[file_id],"merchant_order_id":"ORD-001","confirm_order_link":True})
        assert duplicate.status_code == 409
        assert len(calls)==1
        assert client.get("/api/audit").status_code == 200


def test_paypal_dispute_sync_and_deadline_tracker(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "sync.db"))
    monkeypatch.setattr(main_module, "DEMO", False)
    monkeypatch.setattr(main_module, "MODE", "sandbox")
    monkeypatch.setattr(main_module, "CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(main_module, "CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setattr(main_module, "paypal_list_disputes", lambda n: {"items":[{"dispute_id":"PP-D-SYNC"}]})
    monkeypatch.setattr(main_module, "paypal_get_dispute", lambda did: {"dispute_id":did,"status":"WAITING_FOR_SELLER_RESPONSE","reason":"INR","dispute_life_cycle_stage":"INQUIRY","seller_response_due_date":"2026-11-12T23:59:00Z","evidences":[]})
    with TestClient(app) as client:
        result=client.post("/api/paypal/disputes/sync")
        assert result.status_code == 200, result.text
        assert result.json()["synced"] == 1
        listing=client.get("/api/paypal/disputes").json()
        assert listing[0]["dispute_id"] == "PP-D-SYNC"
        assert listing[0]["deadline_state"] in {"UPCOMING","DUE_WITHIN_3_DAYS","DUE_WITHIN_24_HOURS"}
