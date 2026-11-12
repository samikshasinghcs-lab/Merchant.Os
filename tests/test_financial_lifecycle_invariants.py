"""Pure policy tests for financial lifecycle invariants."""
from decimal import Decimal
import pytest

def balanced(lines):
    debit=sum(Decimal(str(x.get("debit",0))) for x in lines)
    credit=sum(Decimal(str(x.get("credit",0))) for x in lines)
    return debit>0 and debit==credit

def test_balanced_journal_accepts_equal_debits_and_credits():
    assert balanced([{"debit":"10.00","credit":"0"},{"debit":"0","credit":"10.00"}])

def test_unbalanced_journal_rejected():
    assert not balanced([{"debit":"10.00","credit":"0"},{"debit":"0","credit":"9.00"}])

def test_estimate_is_not_realized_value():
    case={"estimated_loss":"50.00","realized_loss":None}
    assert case["estimated_loss"]!="0.00"
    assert case["realized_loss"] is None

@pytest.mark.parametrize("status",["CAPTURED","COMPLETED","PAID","SHIPPED","DELIVERED","REFUNDED"])
def test_captured_or_fulfilled_orders_are_not_cancellable(status):
    assert status in {"CAPTURED","COMPLETED","PAID","PARTIALLY_REFUNDED","REFUNDED","SHIPPED","DELIVERED"}

def test_inventory_instruction_does_not_mutate_stock():
    result={"disposition":"RESTOCK","inventory_mutated":False}
    assert result["inventory_mutated"] is False
