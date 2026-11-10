from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import pytest

from app import paypal


def test_invoice_draft_uses_paypal_invoicing_v2(monkeypatch):
    seen = {}
    monkeypatch.setattr(paypal, "_request", lambda method, path, **kw: seen.update(method=method, path=path, **kw) or {"id": "INV-1"})
    invoice = {"detail": {"currency_code": "USD"}, "items": [{"name": "test"}]}
    result = paypal.create_invoice_draft(invoice, "idem-1")
    assert result["id"] == "INV-1"
    assert seen["method"] == "POST" and seen["path"] == "/v2/invoicing/invoices"
    assert seen["idem"] == "idem-1" and seen["json_body"] == invoice


def test_send_invoice_is_idempotent(monkeypatch):
    seen = {}
    monkeypatch.setattr(paypal, "_request", lambda method, path, **kw: seen.update(method=method, path=path, **kw) or {"status": "SENT"})
    paypal.send_invoice("INV-1", "idem-2")
    assert seen["path"] == "/v2/invoicing/invoices/INV-1/send"
    assert seen["idem"] == "idem-2"
    assert seen["json_body"]["send_to_recipient"] is True


def test_transaction_search_uses_query_parameters(monkeypatch):
    seen = {}
    monkeypatch.setattr(paypal, "_request", lambda method, path, **kw: seen.update(method=method, path=path, **kw) or {"transaction_details": []})
    paypal.search_transactions(start_date="2026-11-01T00:00:00Z", end_date="2026-11-02T00:00:00Z", page_size=25, page=2)
    assert seen["method"] == "GET"
    assert seen["path"] == "/v1/reporting/transactions"
    assert seen["params"]["page"] == 2


def test_vault_setup_token_never_accepts_raw_card_data(monkeypatch):
    seen = {}
    monkeypatch.setattr(paypal, "_request", lambda method, path, **kw: seen.update(method=method, path=path, **kw) or {"id": "SETUP-1"})
    paypal.create_vault_setup_token("merchant_customer", "https://example.test/return", "https://example.test/cancel", "idem-3")
    assert seen["path"] == "/v3/vault/setup-tokens"
    assert "card" not in seen["json_body"]["payment_source"]
    assert seen["json_body"]["payment_source"]["paypal"]["experience_context"]["return_url"].startswith("https://")


def test_vault_payment_token_uses_setup_token_reference(monkeypatch):
    seen = {}
    monkeypatch.setattr(paypal, "_request", lambda method, path, **kw: seen.update(method=method, path=path, **kw) or {"id": "TOKEN-1"})
    paypal.create_vault_payment_token("SETUP-1", "customer-1", "idem-4")
    assert seen["json_body"]["payment_source"]["token"] == {"id": "SETUP-1", "type": "SETUP_TOKEN"}


def test_new_financial_routes_are_sandbox_gated(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DEMO", True)
    with pytest.raises(main.HTTPException) as exc:
        main._require_paypal_financial_api()
    assert exc.value.status_code == 400


def test_invoice_send_requires_explicit_human_approval(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DEMO", False)
    monkeypatch.setattr(main, "MODE", "sandbox")
    monkeypatch.setattr(main, "CLIENT_ID", "id")
    monkeypatch.setattr(main, "CLIENT_SECRET", "secret")
    with pytest.raises(main.HTTPException) as exc:
        main.send_paypal_invoice("INV-123", {"human_approved": False})
    assert exc.value.status_code == 400


def test_transaction_search_rejects_ranges_over_31_days(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DEMO", False)
    monkeypatch.setattr(main, "MODE", "sandbox")
    monkeypatch.setattr(main, "CLIENT_ID", "id")
    monkeypatch.setattr(main, "CLIENT_SECRET", "secret")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=32)
    with pytest.raises(main.HTTPException) as exc:
        main.search_paypal_transactions(start.isoformat(), end.isoformat())
    assert exc.value.status_code == 400


def test_transaction_search_rejects_naive_timestamps(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DEMO", False)
    monkeypatch.setattr(main, "MODE", "sandbox")
    monkeypatch.setattr(main, "CLIENT_ID", "id")
    monkeypatch.setattr(main, "CLIENT_SECRET", "secret")
    with pytest.raises(main.HTTPException) as exc:
        main.search_paypal_transactions("2026-11-01T00:00:00", "2026-11-02T00:00:00")
    assert exc.value.status_code == 400


def test_vault_setup_requires_customer_consent(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DEMO", False)
    monkeypatch.setattr(main, "MODE", "sandbox")
    monkeypatch.setattr(main, "CLIENT_ID", "id")
    monkeypatch.setattr(main, "CLIENT_SECRET", "secret")
    with pytest.raises(main.HTTPException) as exc:
        main.create_paypal_vault_setup_token({"customer_id": "customer-1", "customer_consent": False})
    assert exc.value.status_code == 400
