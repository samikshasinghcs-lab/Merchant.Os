"""Opt-in HTTP end-to-end checks against a disposable MerchantOS environment.

Set MERCHANTOS_E2E_BASE_URL, MERCHANTOS_E2E_TOKEN and
MERCHANTOS_E2E_ORDER_ID. Use a test tenant and non-production PayPal credentials.
"""
import json, os, urllib.request, urllib.error, uuid
import pytest

BASE=os.getenv("MERCHANTOS_E2E_BASE_URL")
TOKEN=os.getenv("MERCHANTOS_E2E_TOKEN")
ORDER=os.getenv("MERCHANTOS_E2E_ORDER_ID")
pytestmark=pytest.mark.skipif(not all([BASE,TOKEN,ORDER]),reason="E2E environment variables are not configured")

def call(path,method="GET",body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(BASE.rstrip("/") + path,data=data,method=method,headers={
        "Authorization":f"Bearer {TOKEN}","Content-Type":"application/json","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=25) as res:
            return res.status,json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read().decode() or "{}")

def test_financial_lifecycle_full_api_path():
    status,overview=call("/api/v1/financial-lifecycle/overview")
    assert status==200 and "order_count" in overview
    status,cost=call(f"/api/v1/financial-lifecycle/orders/{ORDER}/costs","PUT",{
        "cogs":"10.00","shipping_out":"2.00","payment_fee":"1.00","packaging":"0.50","other_cost":"0.00"})
    assert status==200 and cost["source"]=="MERCHANT_ENTERED"
    status,case=call("/api/v1/financial-lifecycle/cases","POST",{
        "order_id":ORDER,"case_type":"RETURN","reason":"E2E test return workflow","estimated_loss":"13.50",
        "recoverable_inventory_estimate":"4.00"})
    assert status==200 and case["status"]=="OPEN"
    status,cases=call("/api/v1/financial-lifecycle/cases")
    assert status==200 and any(x["id"]==case["id"] for x in cases)
    key="e2e-"+uuid.uuid4().hex
    status,journal=call("/api/v1/financial-lifecycle/journal","POST",{
        "currency":"USD","description":"E2E balanced journal","idempotency_key":key,
        "source_type":"E2E","source_id":case["id"],
        "lines":[{"account":"Test Expense","debit":"1.00","credit":"0.00"},
                 {"account":"Test Clearing","debit":"0.00","credit":"1.00"}]})
    assert status==200 and journal["balanced"] is True
    status,recon=call("/api/v1/financial-lifecycle/reconciliation")
    assert status==200 and "items" in recon
    status,intel=call("/api/v1/financial-lifecycle/intelligence")
    assert status==200 and "by_batch" in intel

def test_unknown_or_cross_tenant_order_is_not_disclosed():
    status,body=call("/api/v1/financial-lifecycle/orders/not-an-order/costs","PUT",{
        "cogs":"1","shipping_out":"0","payment_fee":"0","packaging":"0","other_cost":"0"})
    assert status==404
