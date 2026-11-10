"""Canonical transaction fingerprints and explainable feature extraction."""
from __future__ import annotations
from datetime import timezone
from decimal import Decimal
import hashlib, hmac, json
from typing import Any, Iterable
from .models import Transaction

_VOLATILE_METADATA = {"request_id", "trace_id", "received_at", "ingested_at", "debug"}

def _normalise(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if hasattr(value, "isoformat"):
        return value.astimezone(timezone.utc).isoformat() if getattr(value, "tzinfo", None) else value.isoformat()
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)

def canonical_transaction_payload(tx: Transaction, include_customer: bool = True) -> dict[str, Any]:
    metadata = {k: v for k, v in tx.metadata.items() if k not in _VOLATILE_METADATA}
    payload = {
        "transaction_id": tx.transaction_id, "merchant_id": tx.merchant_id,
        "amount": _normalise(tx.amount), "currency": tx.currency,
        "occurred_at": tx.occurred_at.astimezone(timezone.utc).isoformat(),
        "status": tx.status.value, "product_id": tx.product_id,
        "category": tx.category, "channel": tx.channel, "country": tx.country,
        "payment_method": tx.payment_method, "metadata": _normalise(metadata),
    }
    if include_customer:
        payload["customer_id"] = tx.customer_id
    return payload

def canonical_json(value: Any) -> bytes:
    return json.dumps(_normalise(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def transaction_fingerprint(tx: Transaction, key: bytes | None = None, include_customer: bool = True) -> str:
    """Return SHA-256 or HMAC-SHA-256 over a stable canonical representation.

    Use a secret key when fingerprints leave the trusted process; plain hashes of
    low-entropy identifiers can be vulnerable to dictionary guessing.
    """
    body = canonical_json(canonical_transaction_payload(tx, include_customer))
    return hmac.new(key, body, hashlib.sha256).hexdigest() if key else hashlib.sha256(body).hexdigest()

def feature_vector(tx: Transaction) -> dict[str, float]:
    """Small deterministic feature vector; no model training or prediction occurs here."""
    hour = tx.occurred_at.hour + tx.occurred_at.minute / 60.0
    weekday = tx.occurred_at.weekday()
    amount = float(tx.amount)
    return {
        "amount": amount,
        "log_amount": __import__("math").log1p(amount),
        "hour_sin": __import__("math").sin(2 * __import__("math").pi * hour / 24),
        "hour_cos": __import__("math").cos(2 * __import__("math").pi * hour / 24),
        "weekday_sin": __import__("math").sin(2 * __import__("math").pi * weekday / 7),
        "weekday_cos": __import__("math").cos(2 * __import__("math").pi * weekday / 7),
        "is_refund": float(tx.status in {tx.status.REFUNDED, tx.status.PARTIALLY_REFUNDED}),
        "is_disputed": float(tx.status == tx.status.DISPUTED),
    }

def batch_fingerprints(transactions: Iterable[Transaction], key: bytes | None = None) -> dict[str, str]:
    return {tx.transaction_id: transaction_fingerprint(tx, key=key) for tx in transactions}
