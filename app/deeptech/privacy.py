"""Privacy-aware export helpers for analytical and demonstration datasets.

These controls reduce common direct identifiers; they do not guarantee
anonymisation, establish a legal basis, or replace a privacy review.
"""
from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Any, Iterable, Mapping

SENSITIVE_KEYS = {
    "email", "phone", "name", "full_name", "first_name", "last_name",
    "address", "street", "postcode", "postal_code", "customer_name",
    "customer_email", "customer_phone", "ip_address", "date_of_birth",
    "dob", "ssn", "national_id", "tax_id", "passport", "card_number",
    "cvv", "iban", "account_number", "bank_account", "authorization",
    "cookie", "password", "secret", "api_key", "access_token",
    "refresh_token", "session_id",
}
_SECRET_FRAGMENTS = ("password", "secret", "token", "authorization", "api_key", "cookie")
_IDENTIFIER_KEYS = {"customer_id", "user_id", "merchant_user_id", "subject_id"}

def _is_sensitive_key(key: str) -> bool:
    lowered = key.casefold()
    return lowered in SENSITIVE_KEYS or any(fragment in lowered for fragment in _SECRET_FRAGMENTS)

def pseudonymize(value: str, namespace: str, secret: bytes) -> str:
    """Return a stable, keyed pseudonym; a key of at least 128 bits is required."""
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < 16:
        raise ValueError("pseudonymization secret must contain at least 16 bytes")
    if not namespace:
        raise ValueError("namespace is required")
    message = (namespace + ":" + str(value)).encode("utf-8")
    return hmac.new(bytes(secret), message, sha256).hexdigest()[:24]

def privacy_transform(record: Mapping[str, Any], secret: bytes, preserve_keys: Iterable[str] = ()) -> dict[str, Any]:
    """Minimise a mapping and pseudonymise common identifiers.

    Explicit preservation never overrides credential/secret filtering. Unknown
    free text and rare combinations may still contain identifying information.
    """
    keep = set(preserve_keys)
    result: dict[str, Any] = {}
    for key, value in record.items():
        lowered = str(key).casefold()
        if _is_sensitive_key(str(key)):
            continue
        if key in keep:
            result[key] = value
        elif lowered in _IDENTIFIER_KEYS and value is not None:
            result[key] = pseudonymize(str(value), lowered, secret)
        elif isinstance(value, Mapping):
            result[key] = privacy_transform(value, secret)
        elif isinstance(value, list):
            result[key] = [privacy_transform(item, secret) if isinstance(item, Mapping) else item for item in value]
        else:
            result[key] = value
    return result
