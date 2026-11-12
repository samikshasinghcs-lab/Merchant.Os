"""Unit tests for spec additions. Written without being run in the editing environment: run in CI."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from decimal import Decimal
from app import financial_lifecycle as fl

def _order(**k):
    base=dict(amount=100,delivered_at=None,shipped_at=None,hygiene_item=None)
    base.update(k); return NS(**base)
def _case(kind="RETURN",req="50"):
    return NS(case_type=kind,requested_amount=Decimal(req),estimated_loss=Decimal("40"),recoverable_inventory_estimate=Decimal("10"))

def test_missing_delivery_date_is_unknown_not_eligible():
    r=fl._grid_signals(_case(),_order(),1)
    assert r["policy_result"].startswith("UNKNOWN")

def test_return_window_failure():
    d=datetime.now(timezone.utc)-timedelta(days=30)
    r=fl._grid_signals(_case(),_order(delivered_at=d),1)
    assert "RETURN_WINDOW" in r["policy_result"] and r["ai_suggestion"]=="REJECT_REVIEW"

def test_refund_cap():
    r=fl._grid_signals(_case(req="500"),_order(),1)
    assert "REFUND_CAP" in r["policy_result"]

def test_hygiene_and_cancel_rules():
    assert "OPENED_HYGIENE_ITEM" in fl._grid_signals(_case("EXCHANGE"),_order(hygiene_item=True,delivered_at=datetime.now(timezone.utc)),1)["policy_result"]
    assert "CANCEL_BEFORE_SHIPPING" in fl._grid_signals(_case("CANCELLATION"),_order(shipped_at=datetime.now(timezone.utc)),0)["policy_result"]

def test_no_evidence_holds():
    assert fl._grid_signals(_case(),_order(),0)["ai_suggestion"]=="HOLD_FOR_EVIDENCE"

def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MERCHANTOS_LLM_ENABLED",raising=False)
    assert fl._llm_advice({"case_type":"RETURN"}) is None
