import os
from app.release_readiness import readiness_report


def test_development_readiness_does_not_claim_production():
    old = os.environ.get("APP_ENV")
    os.environ["APP_ENV"] = "development"
    try:
        report = readiness_report()
        assert report["ready"] is True
        assert report["release_scope"] == "local development only"
    finally:
        if old is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old


def test_production_readiness_fails_closed_by_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for key in ["AUTH_REQUIRED", "JWT_SECRET_KEY", "DEMO_MODE", "PAYPAL_MODE",
                "PAYPAL_EXECUTION_ENABLED", "SEED_DEMO_DATA", "DATABASE_URL", "DATABASE_PATH",
                "MERCHANTOS_SINGLE_TENANT_PILOT", "PUBLIC_APP_URL", "RENDER_API_KEY",
                "WORKFLOW_SERVICE_SLUG", "MERCHANTOS_WORKFLOW_SHARED_SECRET",
                "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID", "MERCHANTOS_CREDENTIALS_KEY", "EVIDENCE_UPLOAD_DIR"]:
        monkeypatch.delenv(key, raising=False)
    report = readiness_report()
    assert report["ready"] is False
    assert report["financial_execution"] == "disabled"
    assert report["release_scope"].startswith("single-merchant")
    assert any(not item["passed"] for item in report["checks"])


def test_production_readiness_accepts_complete_sandbox_pilot_config(monkeypatch):
    values = {
        "APP_ENV": "production", "AUTH_REQUIRED": "true",
        "JWT_SECRET_KEY": "a" * 48, "DEMO_MODE": "false", "PAYPAL_MODE": "sandbox",
        "PAYPAL_EXECUTION_ENABLED": "false", "SEED_DEMO_DATA": "false", "DATABASE_URL": "postgresql+psycopg://u:p@host/db",
        "DATABASE_PATH": "/var/data/merchantos.db", "MERCHANTOS_SINGLE_TENANT_PILOT": "true",
        "PUBLIC_APP_URL": "https://merchantos.example.com", "RENDER_API_KEY": "render-key",
        "WORKFLOW_SERVICE_SLUG": "merchantos-events", "MERCHANTOS_WORKFLOW_SHARED_SECRET": "s" * 48,
        "PAYPAL_CLIENT_ID": "sandbox-client", "PAYPAL_CLIENT_SECRET": "sandbox-secret",
        "PAYPAL_WEBHOOK_ID": "sandbox-webhook-id",
        "MERCHANTOS_CREDENTIALS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "EVIDENCE_UPLOAD_DIR": "/var/data/merchantos-evidence",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    report = readiness_report()
    assert report["ready"] is True
    assert report["financial_execution"] == "disabled"


def test_production_readiness_rejects_live_paypal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYPAL_MODE", "live")
    report = readiness_report()
    assert not next(x for x in report["checks"] if x["name"] == "paypal_environment")["passed"]


def test_production_readiness_requires_external_review_acknowledgements(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", "true")
    monkeypatch.setenv("MERCHANTOS_EXTERNAL_REVIEW_DPA_ACK", "false")
    monkeypatch.setenv("MERCHANTOS_EXTERNAL_REVIEW_REDACTION_ACK", "false")
    report = readiness_report()
    check = next(x for x in report["checks"] if x["name"] == "external_review_processing_ack")
    assert check["passed"] is False


def test_production_readiness_rejects_evidence_storage_at_static_root(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    static_root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "app", "static"))
    monkeypatch.setenv("EVIDENCE_UPLOAD_DIR", static_root)
    report = readiness_report()
    check = next(x for x in report["checks"] if x["name"] == "private_evidence_storage_path")
    assert check["passed"] is False


def test_production_readiness_rejects_evidence_storage_nested_under_static(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    static_root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "app", "static"))
    nested = os.path.join(static_root, "uploads")
    monkeypatch.setenv("EVIDENCE_UPLOAD_DIR", nested)
    report = readiness_report()
    check = next(x for x in report["checks"] if x["name"] == "private_evidence_storage_path")
    assert check["passed"] is False


def test_production_readiness_rejects_symlink_evidence_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    real_storage = tmp_path / "private-storage"
    real_storage.mkdir(mode=0o700)
    link = tmp_path / "evidence-link"
    link.symlink_to(real_storage, target_is_directory=True)
    monkeypatch.setenv("EVIDENCE_UPLOAD_DIR", str(link))
    report = readiness_report()
    check = next(x for x in report["checks"] if x["name"] == "private_evidence_storage_path")
    assert check["passed"] is False


def test_sandbox_execution_requires_explicit_ack(monkeypatch):
    from app.release_readiness import readiness_report
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MERCHANTOS_SANDBOX_REFUND_EXECUTION_ACK", "false")
    report=readiness_report()
    gate=next(x for x in report["checks"] if x["name"]=="financial_execution")
    assert gate["passed"] is False

def test_sandbox_execution_ack_does_not_enable_live_mode(monkeypatch):
    from app.release_readiness import readiness_report
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MERCHANTOS_SANDBOX_REFUND_EXECUTION_ACK", "true")
    report=readiness_report()
    gate=next(x for x in report["checks"] if x["name"]=="financial_execution")
    assert gate["passed"] is True
    assert report["financial_execution"]=="sandbox_only_enabled"
