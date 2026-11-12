import json
from pathlib import Path
import pytest

from app.workflow_events import sanitize_paypal_event


def test_paypal_event_sanitizer_keeps_operational_fields_only():
    raw = {
        "id": "WH-123", "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "create_time": "2026-11-10T12:00:00Z",
        "resource": {"id": "CAP-9", "status": "COMPLETED",
                     "amount": {"value": "12.00", "currency_code": "USD"},
                     "payer": {"email_address": "private@example.com"},
                     "shipping": {"address": {"line1": "private"}}},
    }
    safe = sanitize_paypal_event(raw)
    assert safe["event_id"] == "WH-123"
    assert safe["resource_id"] == "CAP-9"
    assert "payer" not in json.dumps(safe)
    assert "private@example.com" not in json.dumps(safe)
    assert "shipping" not in json.dumps(safe)


def test_paypal_event_sanitizer_rejects_missing_identity():
    with pytest.raises(ValueError):
        sanitize_paypal_event({"event_type": "PAYMENT.CAPTURE.COMPLETED"})


def test_sponsor_config_declares_community_packages_and_workflow():
    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "frontend/package.json").read_text())
    deps = package["dependencies"]
    assert deps["ag-grid-react"] == "36.3.0"
    assert "@bryntum/scheduler-react-community" not in deps  # timeline is native React; no private license/token needed
    timeline = (root / "frontend/src/pages/ExecutionTimeline.tsx").read_text()
    assert "execution-timeline" in timeline
    blueprint = (root / "render.yaml").read_text()
    assert "type: workflow" in blueprint
    assert "python -m app.render_workflows" in blueprint
    assert "WORKFLOW_SERVICE_SLUG" in blueprint
