"""Read-only MerchantOS MCP server for PayPal context and reconciliation lookups.

Run: python -m app.mcp_server
The MCP surface deliberately excludes refunds, captures, invoice sends and vault writes.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised only when optional dependency absent
    raise SystemExit("Install the MCP SDK with `pip install 'mcp>=1.9,<2'` to run this server") from exc

from .config import DEMO, MODE, CLIENT_ID, CLIENT_SECRET
from .paypal import search_transactions, get_invoice, get_dispute, PayPalError

mcp = FastMCP("MerchantOS PayPal Read-only Context")


def _guard():
    if DEMO or MODE != "sandbox" or not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("MCP PayPal tools require DEMO_MODE=false, PAYPAL_MODE=sandbox and configured Sandbox credentials")


@mcp.tool()
def paypal_api_catalog() -> dict:
    """Return the versioned PayPal API capability catalogue and safety boundaries."""
    return {
        "orders": ["POST /v2/checkout/orders", "POST /v2/checkout/orders/{id}/capture"],
        "payments": ["POST /v2/payments/captures/{id}/refund"],
        "disputes": ["GET /v1/customer/disputes", "GET /v1/customer/disputes/{id}"],
        "invoicing": ["POST /v2/invoicing/invoices", "POST /v2/invoicing/invoices/{id}/send", "GET /v2/invoicing/invoices/{id}"],
        "transaction_search": ["GET /v1/reporting/transactions"],
        "vault": ["POST /v3/vault/setup-tokens", "POST /v3/vault/payment-tokens"],
        "guardrails": ["Sandbox only", "MCP is read-only", "No PAN/CVV handling", "Financial writes require the authenticated MerchantOS API and human approval"],
    }


@mcp.tool()
def search_paypal_transactions(days: int = 7, page_size: int = 25) -> dict:
    """Search recent Sandbox transactions. Reporting may lag up to three hours."""
    _guard()
    if not 1 <= days <= 31:
        raise ValueError("days must be between 1 and 31")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    try:
        result = search_transactions(start_date=start.isoformat().replace("+00:00", "Z"),
            end_date=end.isoformat().replace("+00:00", "Z"), page_size=page_size, page=1)
    except PayPalError as exc:
        raise RuntimeError(str(exc)) from exc
    return {"transaction_details": result.get("transaction_details", []),
            "total_items": result.get("total_items"), "total_pages": result.get("total_pages"),
            "reporting_lag_note": "PayPal reporting can take up to three hours to reflect executed transactions."}


@mcp.tool()
def get_paypal_invoice(invoice_id: str) -> dict:
    """Retrieve a PayPal Sandbox invoice by its PayPal invoice ID."""
    _guard()
    if not invoice_id or len(invoice_id) > 80 or not invoice_id.replace("-", "").isalnum():
        raise ValueError("Invalid invoice ID")
    try:
        return get_invoice(invoice_id)
    except PayPalError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
def get_paypal_dispute(dispute_id: str) -> dict:
    """Retrieve a PayPal Sandbox dispute by its PayPal dispute ID."""
    _guard()
    if not dispute_id or len(dispute_id) > 80 or not dispute_id.replace("-", "").isalnum():
        raise ValueError("Invalid dispute ID")
    try:
        return get_dispute(dispute_id)
    except PayPalError as exc:
        raise RuntimeError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run(transport="stdio")
