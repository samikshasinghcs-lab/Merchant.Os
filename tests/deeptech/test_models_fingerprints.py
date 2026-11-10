from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.deeptech.models import Transaction
from app.deeptech.fingerprints import transaction_fingerprint, canonical_transaction_payload, feature_vector

def test_transaction_normalizes_decimal_and_timezone(make_tx):
    tx=make_tx(amount="10.500")
    assert tx.amount == Decimal("10.500") and tx.occurred_at.tzinfo is not None

def test_rejects_naive_timestamp(make_tx):
    with pytest.raises(ValueError): make_tx(occurred_at=datetime(2026,1,1))

def test_rejects_negative_amount(make_tx):
    with pytest.raises(ValueError): make_tx(amount="-1")

def test_rejects_bad_currency(make_tx):
    with pytest.raises(ValueError): make_tx(currency="US")

def test_fingerprint_stable(make_tx):
    assert transaction_fingerprint(make_tx()) == transaction_fingerprint(make_tx())

def test_fingerprint_changes_on_amount(make_tx):
    assert transaction_fingerprint(make_tx(amount="10")) != transaction_fingerprint(make_tx(amount="11"))

def test_hmac_fingerprint_differs(make_tx):
    assert transaction_fingerprint(make_tx(),key=b"secret") != transaction_fingerprint(make_tx())

def test_volatile_metadata_ignored(make_tx):
    a=make_tx(metadata={"request_id":"a","source":"api"}); b=make_tx(metadata={"request_id":"b","source":"api"})
    assert transaction_fingerprint(a)==transaction_fingerprint(b)

def test_customer_can_be_excluded(make_tx):
    a=make_tx(customer_id="a"); b=make_tx(customer_id="b")
    assert transaction_fingerprint(a,include_customer=False)==transaction_fingerprint(b,include_customer=False)

def test_features_are_finite(make_tx):
    assert all(abs(v)<1000 for v in feature_vector(make_tx()).values())
