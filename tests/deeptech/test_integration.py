from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app.deeptech.integration import (
    MerchantScopeError,
    analyze_merchant_transactions,
)
from app.deeptech.models import Transaction, TransactionStatus


def tx(identifier, amount, *, merchant="m-1", customer="c-1", day=1):
    return Transaction(
        transaction_id=identifier,
        merchant_id=merchant,
        amount=Decimal(str(amount)),
        currency="USD",
        occurred_at=datetime(2026, 1, day, 12, tzinfo=timezone.utc),
        status=TransactionStatus.COMPLETED,
        customer_id=customer,
        product_id="p-1",
        channel="web",
    )


def test_integration_uses_history_only_as_anomaly_baseline():
    history = [tx(f"h-{i}", 10 + i / 10, day=(i % 28) + 1) for i in range(12)]
    observed = [tx("new-1", 500, day=29)]
    result = analyze_merchant_transactions("m-1", history, observed)
    assert result["methodology"]["baseline_transaction_count"] == 12
    assert result["methodology"]["observations_excluded_from_baseline"] is True
    assert result["transactions"][0]["fingerprint"]
    assert result["transactions"][0]["anomaly"]["transaction_id"] == "new-1"
    assert result["graph"]["node_count"] >= 3


def test_integration_rejects_cross_merchant_rows():
    with pytest.raises(MerchantScopeError):
        analyze_merchant_transactions(
            "m-1", [tx("h-1", 10, merchant="m-2")], [tx("o-1", 12)]
        )


def test_integration_rejects_duplicate_ids_between_history_and_observed():
    row = tx("same", 10)
    with pytest.raises(ValueError, match="unique"):
        analyze_merchant_transactions("m-1", [row], [row])


def test_integration_requires_observed_transactions():
    with pytest.raises(ValueError, match="observed"):
        analyze_merchant_transactions("m-1", [tx("h-1", 10)], [])


def test_integration_excludes_customer_identifier_from_fingerprint_payload():
    row = tx("o-1", 12, customer="private-customer-id")
    result = analyze_merchant_transactions("m-1", [], [row])
    assert result["transactions"][0]["fingerprint"]
    assert "private-customer-id" not in str(result)
    assert result["transactions"][0]["anomaly"] is None


def test_integration_rejects_blank_merchant_scope():
    with pytest.raises(ValueError, match="merchant_id"):
        analyze_merchant_transactions(" ", [], [tx("o-1", 12)])
