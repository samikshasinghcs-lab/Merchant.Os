"""Deterministic financial policy and approval primitives.

This module deliberately does not call PayPal. It evaluates a verified snapshot,
creates a canonical approval digest, and validates maker/checker separation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re

_CURRENCY = re.compile(r"^[A-Z]{3}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CENT = Decimal("0.01")

@dataclass(frozen=True)
class RefundDecision:
    allowed: bool
    reasons: tuple[str, ...]
    amount: str
    currency: str
    remaining_capture_balance: str

    def as_dict(self):
        return asdict(self)


def _money(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} must be a valid decimal amount")
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    rounded = result.quantize(_CENT, rounding=ROUND_HALF_UP)
    if result != rounded:
        raise ValueError(f"{field} must not contain fractional cents")
    return rounded


def evaluate_refund(*, capture_id: str, amount, currency: str,
                    capture_amount, capture_currency: str,
                    already_refunded="0.00", daily_total="0.00",
                    max_refund="2000.00", daily_cap="10000.00",
                    provider_status="COMPLETED", reconciliation_verified=False) -> RefundDecision:
    """Evaluate refund eligibility using provider-reconciled facts only.

    A client-supplied status is not provider verification: callers must set
    reconciliation_verified only after a successful canonical PayPal read.
    """
    capture_id = str(capture_id or "").strip()
    if not _ID.fullmatch(capture_id):
        raise ValueError("capture_id is invalid")
    currency = str(currency or "").upper()
    capture_currency = str(capture_currency or "").upper()
    if not _CURRENCY.fullmatch(currency) or not _CURRENCY.fullmatch(capture_currency):
        raise ValueError("currency must be a three-letter ISO code")
    requested = _money(amount, "amount")
    original = _money(capture_amount, "capture_amount")
    refunded = _money(already_refunded, "already_refunded")
    today_total = _money(daily_total, "daily_total")
    per_refund_limit = _money(max_refund, "max_refund")
    daily_limit = _money(daily_cap, "daily_cap")
    reasons = []
    if not reconciliation_verified:
        reasons.append("CANONICAL_PAYPAL_RECONCILIATION_REQUIRED")
    if str(provider_status or "").upper() not in {"COMPLETED", "PARTIALLY_REFUNDED"}:
        reasons.append("CAPTURE_NOT_REFUNDABLE_STATUS")
    if currency != capture_currency:
        reasons.append("CURRENCY_MISMATCH")
    if requested <= 0:
        reasons.append("AMOUNT_MUST_BE_POSITIVE")
    if original <= 0 or refunded < 0 or refunded > original:
        reasons.append("INVALID_CAPTURE_BALANCE")
    remaining = max(Decimal("0.00"), original - refunded)
    if requested > remaining:
        reasons.append("REFUND_EXCEEDS_REMAINING_CAPTURE_BALANCE")
    if requested > per_refund_limit:
        reasons.append("PER_REFUND_LIMIT_EXCEEDED")
    if today_total + requested > daily_limit:
        reasons.append("DAILY_REFUND_LIMIT_EXCEEDED")
    return RefundDecision(not reasons, tuple(reasons), f"{requested:.2f}", currency, f"{remaining:.2f}")


def approval_digest(*, tenant_id: str, capture_id: str, amount: str,
                    currency: str, reason: str, policy_version="refund-policy-v1") -> str:
    """Stable digest binds approval to exact tenant, capture, amount and reason."""
    payload = {"tenant_id": tenant_id, "capture_id": capture_id,
               "amount": f"{_money(amount, 'amount'):.2f}",
               "currency": currency.upper(), "reason": reason.strip(),
               "policy_version": policy_version}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def validate_approver(*, requester_id: str, approver_id: str, role: str,
                      approval_digest_matches: bool, status: str) -> None:
    if status != "PENDING_APPROVAL":
        raise ValueError("Approval request is not pending")
    if requester_id == approver_id:
        raise PermissionError("Maker-checker policy: requester cannot approve their own request")
    if role not in {"OWNER", "ADMIN"}:
        raise PermissionError("OWNER or ADMIN role required to approve financial actions")
    if not approval_digest_matches:
        raise ValueError("Approval payload digest mismatch")
