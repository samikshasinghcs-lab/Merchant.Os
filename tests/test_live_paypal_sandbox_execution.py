"""Explicitly opt-in one-time PayPal Sandbox refund smoke test.

Requires a pre-reconciled, independently approved refund approval. This test can
move Sandbox funds only; it refuses to run without the explicit confirmation flag.
"""
import json, os, urllib.request, urllib.error
import pytest

BASE = os.getenv("MERCHANTOS_LIVE_BASE_URL")
TOKEN = os.getenv("MERCHANTOS_LIVE_TOKEN")
APPROVAL_ID = os.getenv("MERCHANTOS_LIVE_APPROVAL_ID")
CONFIRM = os.getenv("MERCHANTOS_LIVE_REFUND_CONFIRM")
pytestmark = pytest.mark.skipif(
    not all([BASE, TOKEN, APPROVAL_ID]) or CONFIRM != "SANDBOX_ONLY",
    reason="Set live Sandbox URL/token/approved approval ID and MERCHANTOS_LIVE_REFUND_CONFIRM=SANDBOX_ONLY to opt in",
)


def call(path, method="GET"):
    req = urllib.request.Request(BASE.rstrip("/") + path, method=method, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def test_one_independently_approved_sandbox_refund_is_provider_confirmed():
    status, approvals = call("/api/v1/operations/financial/refund-approvals")
    assert status == 200
    row = next((item for item in approvals if item.get("id") == APPROVAL_ID), None)
    assert row, "Approval ID was not found in the authenticated tenant"
    assert row.get("status") == "APPROVED", "Approval must already be independently approved"
    assert row.get("requester_id") and row.get("approver_id") != row.get("requester_id"), "Maker-checker must be satisfied"
    status, result = call(f"/api/v1/operations/financial/refund-approvals/{APPROVAL_ID}/execute", "POST")
    assert status == 200, result
    assert result.get("environment") == "sandbox", result
    assert result.get("provider") == "PAYPAL", result
    assert result.get("provider_refund_id"), result
    assert result.get("provider_status") in {"COMPLETED", "PENDING"}, result
    assert result.get("status") in {"SUCCEEDED", "SUBMITTED"}, result
