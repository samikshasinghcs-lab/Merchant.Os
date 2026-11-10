from datetime import datetime, timezone, timedelta
from app.dispute_intelligence import deadline_summary, evidence_readiness

def test_deadline_urgency_windows():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert deadline_summary((now + timedelta(hours=2)).isoformat(), now)["state"] == "DUE_WITHIN_6_HOURS"
    assert deadline_summary((now - timedelta(seconds=1)).isoformat(), now)["state"] == "OVERDUE"

def test_missing_paypal_requested_evidence_blocks_readiness():
    result = evidence_readiness({"payload": {"status": "WAITING_FOR_SELLER_RESPONSE", "evidences": []}}, [], None, None)
    assert not result["ready"]
    assert any("requested-from-seller" in x for x in result["missing_requirements"])

def test_file_order_and_integrity_must_match():
    dispute = {"payload": {"status": "WAITING_FOR_SELLER_RESPONSE", "evidences": [{"source": "REQUESTED_FROM_SELLER", "evidence_type": "PROOF_OF_DELIVERY"}]}}
    order = {"capture_id": "CAP-1", "paypal_order_id": "ORD-1"}
    files = [{"file_id": "F1", "order_id": "O-1", "mime_type": "application/pdf", "size_bytes": 1024}]
    result = evidence_readiness(dispute, files, "O-1", order, {"F1": {"integrity": "HASH_MATCH"}})
    assert result["ready"]
    bad = evidence_readiness(dispute, files, "O-2", order, {"F1": {"integrity": "HASH_MISMATCH"}})
    assert not bad["ready"]

def test_disputed_transaction_mismatch_blocks():
    dispute = {"payload": {"status": "WAITING_FOR_SELLER_RESPONSE", "evidences": [{"source": "REQUESTED_FROM_SELLER", "evidence_type": "PROOF_OF_DELIVERY"}], "transaction_info": {"transaction_id": "OTHER"}}}
    order = {"capture_id": "CAP-1", "paypal_order_id": "ORD-1"}
    files = [{"file_id": "F1", "order_id": "O-1", "mime_type": "application/pdf", "size_bytes": 1024}]
    result = evidence_readiness(dispute, files, "O-1", order, {"F1": {"integrity": "HASH_MATCH"}})
    assert not result["ready"]
    assert any("transaction identifiers" in x for x in result["missing_requirements"])
