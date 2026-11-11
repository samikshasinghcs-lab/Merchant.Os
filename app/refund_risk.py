"""Read-only DeepTech risk signals for a refund's order.

Compares one order against the merchant's other orders using the explainable
robust-statistics detector. Advisory only: it never approves, blocks or
executes anything, and any failure returns None so refunds keep working.
"""
from .db import db
from .deeptech import analyze_merchant_transactions
from .deeptech.models import TransactionStatus

MERCHANT_ID = "pilot-merchant"
_VALID = {s.value for s in TransactionStatus}


def _tx(row):
    status = str(row["payment_status"] or "COMPLETED").upper()
    return {
        "transaction_id": row["id"],
        "merchant_id": MERCHANT_ID,
        "amount": row["amount"],
        "currency": row["currency"] or "USD",
        "created_at": row["created_at"],
        "status": status if status in _VALID else "COMPLETED",
        "customer_id": row["customer_id"],
        "product_id": row["product"],
    }


def risk_for_order(order_id):
    try:
        with db() as c:
            rows = c.execute("SELECT * FROM orders").fetchall()
        target = next((r for r in rows if r["id"] == order_id), None)
        if target is None:
            return None
        history = [_tx(r) for r in rows if r["id"] != order_id]
        result = analyze_merchant_transactions(
            MERCHANT_ID, history, [_tx(target)])
        finding = result["transactions"][0]["anomaly"]
        if not finding:
            return None
        return {
            "score": round(float(finding["score"]), 1),
            "severity": finding["severity"],
            "signals": list(finding["signals"]),
            "baseline_orders": result["methodology"]["baseline_transaction_count"],
            "note": "Advisory signal from explainable statistics; not a fraud verdict.",
        }
    except Exception:
        return None
