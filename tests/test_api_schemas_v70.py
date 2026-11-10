from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.api_schemas import TenantOrderCreate, TenantReviewCreate


def test_order_schema_accepts_bounded_decimal_and_normalizes_currency():
    body = TenantOrderCreate.model_validate({"amount": "120.50", "currency": "usd", "product": "Widget"})
    assert body.amount == Decimal("120.50")
    assert body.currency == "USD"


@pytest.mark.parametrize("payload", [
    {"amount": "0", "currency": "USD"},
    {"amount": "-1", "currency": "USD"},
    {"amount": "1.001", "currency": "USD"},
    {"amount": "NaN", "currency": "USD"},
    {"amount": "1", "currency": "US D"},
    {"amount": "1", "currency": "USD", "tenant_id": "attacker-controlled"},
    {"amount": "1", "currency": "USD", "payment_status": "COMPLETED"},
])
def test_invalid_order_input_is_rejected(payload):
    with pytest.raises(ValidationError):
        TenantOrderCreate.model_validate(payload)


def test_review_rejects_blank_or_oversized_text_and_server_owned_fields():
    with pytest.raises(ValidationError):
        TenantReviewCreate.model_validate({"text": "   "})
    with pytest.raises(ValidationError):
        TenantReviewCreate.model_validate({"text": "x" * 10_001})
    with pytest.raises(ValidationError):
        TenantReviewCreate.model_validate({"text": "ok", "severity": "CRITICAL"})


def test_review_rating_is_strict_and_bounded():
    assert TenantReviewCreate.model_validate({"text": "Good", "rating": 5}).rating == 5
    with pytest.raises(ValidationError):
        TenantReviewCreate.model_validate({"text": "Good", "rating": "5"})
    with pytest.raises(ValidationError):
        TenantReviewCreate.model_validate({"text": "Good", "rating": 6})


def test_review_cannot_reference_order_outside_current_tenant(monkeypatch):
    from contextlib import contextmanager
    from fastapi import HTTPException
    from app import tenant_api

    class Session:
        def scalar(self, statement):
            sql = str(statement)
            assert "merchant_orders.tenant_id" in sql
            return None

    @contextmanager
    def fake_tenant_session(tenant_id):
        assert tenant_id == "tenant-a"
        yield Session()

    monkeypatch.setattr(tenant_api, "tenant_session", fake_tenant_session)
    body = TenantReviewCreate.model_validate({"text": "A review", "order_id": "order-from-another-tenant"})
    with pytest.raises(HTTPException) as exc:
        tenant_api.create_review(body, {"tenant_id": "tenant-a"})
    assert exc.value.status_code == 404
