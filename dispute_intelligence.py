"""Deterministic dispute deadline and evidence-readiness intelligence.

This module never decides whether a claim is true or predicts a dispute outcome.
It checks operational completeness and highlights missing evidence for human review.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

SUPPORTED_PAYPAL_EVIDENCE = {
    "PROOF_OF_FULFILLMENT", "PROOF_OF_DELIVERY", "PROOF_OF_REFUND",
    "PROOF_OF_RETURN", "ITEM_DESCRIPTION", "BILLING_AGREEMENT",
    "CANCELLATION_POLICY", "TRACKING_NUMBER", "OTHER",
}

def deadline_summary(due_at: str | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if not due_at:
        return {"state": "UNKNOWN", "seconds_remaining": None, "action_required": True}
    try:
        due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        seconds = int((due - now).total_seconds())
    except (TypeError, ValueError):
        return {"state": "UNKNOWN", "seconds_remaining": None, "action_required": True}
    if seconds < 0: state = "OVERDUE"
    elif seconds <= 6 * 3600: state = "DUE_WITHIN_6_HOURS"
    elif seconds <= 24 * 3600: state = "DUE_WITHIN_24_HOURS"
    elif seconds <= 3 * 86400: state = "DUE_WITHIN_3_DAYS"
    else: state = "UPCOMING"
    return {"state": state, "seconds_remaining": seconds, "action_required": state != "UPCOMING"}

def evidence_readiness(dispute: dict, files: list[dict], merchant_order_id: str | None,
                       order: dict | None, integrity_results: dict[str, dict] | None = None) -> dict:
    payload = dispute.get("payload") or dispute.get("payload_json") or {}
    if isinstance(payload, str):
        import json
        try: payload = json.loads(payload)
        except ValueError: payload = {}
    status = str(payload.get("status") or dispute.get("status") or "").upper()
    requested = [x for x in payload.get("evidences", []) if x.get("source") == "REQUESTED_FROM_SELLER"]
    missing = []
    if status != "WAITING_FOR_SELLER_RESPONSE": missing.append("Dispute is not waiting for seller response")
    if not requested: missing.append("PayPal has not supplied requested-from-seller evidence types")
    if not merchant_order_id or not order: missing.append("A valid MerchantOS order must be manually linked")
    if not files: missing.append("At least one evidence file is required")
    allowed_types = sorted({str(x.get("evidence_type")) for x in requested if x.get("evidence_type")})
    file_checks = []
    total = 0
    for f in files:
        fid = str(f.get("file_id") or f.get("id") or "")
        reasons = []
        if f.get("order_id") != merchant_order_id: reasons.append("ORDER_MISMATCH")
        if f.get("mime_type") not in {"application/pdf", "image/jpeg", "image/png", "image/gif"}: reasons.append("UNSUPPORTED_MIME")
        size = int(f.get("size_bytes") or 0); total += size
        if size <= 0 or size >= 10 * 1024 * 1024: reasons.append("INVALID_FILE_SIZE")
        integrity = (integrity_results or {}).get(fid, {}).get("integrity")
        if integrity != "HASH_MATCH": reasons.append("INTEGRITY_NOT_VERIFIED")
        file_checks.append({"file_id": fid, "ready": not reasons, "issues": reasons})
    if total > 50 * 1024 * 1024: missing.append("Combined evidence exceeds PayPal's 50 MB request limit")
    if file_checks and any(not x["ready"] for x in file_checks): missing.append("One or more evidence files failed validation")
    tx_ids = set()
    for tx in payload.get("disputed_transactions", []) or []:
        for key in ("transaction_id", "seller_transaction_id", "buyer_transaction_id"):
            if tx.get(key): tx_ids.add(str(tx[key]))
    tx_info = payload.get("transaction_info") or {}
    for key in ("transaction_id", "paypal_reference_id"):
        if tx_info.get(key): tx_ids.add(str(tx_info[key]))
    if order and tx_ids and not ({str(order.get("capture_id") or ""), str(order.get("paypal_order_id") or "")} & tx_ids):
        missing.append("Linked order does not match PayPal transaction identifiers")
    return {"ready": not missing, "dispute_status": status, "requested_evidence_types": allowed_types,
            "file_checks": file_checks, "total_bytes": total, "missing_requirements": missing,
            "human_review_required": True,
            "disclaimer": "Readiness is an operational completeness check, not proof that evidence is truthful, sufficient, or likely to win."}
