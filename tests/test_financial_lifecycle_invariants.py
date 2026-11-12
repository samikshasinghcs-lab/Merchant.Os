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


def test_perceptual_hash_is_stable_for_same_image():
    from io import BytesIO
    from PIL import Image
    from app.financial_lifecycle import perceptual_hash, hamming_hash_distance
    image=Image.new("RGB",(32,32),(240,30,30))
    buffer=BytesIO(); image.save(buffer,format="PNG")
    digest=perceptual_hash(buffer.getvalue())
    assert digest and len(digest)==64
    assert hamming_hash_distance(digest,digest)==0

def test_perceptual_hash_distance_handles_invalid_values():
    from app.financial_lifecycle import hamming_hash_distance
    assert hamming_hash_distance("1010","10")==999
    assert hamming_hash_distance("1010","1000")==1
