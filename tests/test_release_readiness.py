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
                "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID", "MERCHANTOS_CREDENTIALS_KEY"]:
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
