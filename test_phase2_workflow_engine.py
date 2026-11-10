import pytest
from app.workflow_engine import classify_paypal_event, build_reconciliation_work_item
from app.workflow_events import sanitize_paypal_event

def test_capture_completed_routes_to_reconciliation_not_financial_write():
    item = build_reconciliation_work_item({"event_id":"WH-1", "event_type":"PAYMENT.CAPTURE.COMPLETED"})
    assert item["status"] == "RECONCILIATION_REQUIRED"
    assert item["action"] == "reconcile_capture"
    assert item["financial_write_authorized"] is False

def test_dispute_event_routes_to_sync():
    plan = classify_paypal_event("CUSTOMER.DISPUTE.CREATED")
    assert plan.domain == "dispute"
    assert plan.action == "sync_dispute"

def test_unknown_event_is_quarantined():
    item = build_reconciliation_work_item({"event_id":"WH-2", "event_type":"SOME.NEW.EVENT"})
    assert item["status"] == "IGNORED_UNSUPPORTED"
    assert item["requires_provider_reconciliation"] is False

def test_event_identity_required():
    with pytest.raises(ValueError):
        build_reconciliation_work_item({"event_type":"PAYMENT.CAPTURE.COMPLETED"})

def test_event_plan_is_deterministic_and_case_normalized():
    assert classify_paypal_event("payment.capture.refunded") == classify_paypal_event("PAYMENT.CAPTURE.REFUNDED")
