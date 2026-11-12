from decimal import Decimal
from app.financial_lifecycle import financial_preview


def test_restock_preview_uses_explicit_formula_and_fee_disclosure():
    result = financial_preview({
        "currency": "INR", "cogs": "1000.00", "refund": "500.00",
        "return_shipping": "40.00", "handling": "20.00", "payment_fee": "15.00",
        "write_off": "0.00", "disposition": "RESTOCK"
    }, {"role": "OWNER"})
    assert result["recovered_item_value"] == "1000.00"
    assert result["net_recovery"] == "425.00"
    assert "does not assert" in result["source_disclosure"]


def test_refurbish_preview_deducts_repair_cost():
    result = financial_preview({
        "cogs": "1000.00", "refund": "0", "return_shipping": "0",
        "handling": "0", "payment_fee": "0", "repair_cost": "100.00",
        "write_off": "0", "disposition": "REFURBISH"
    }, {"role": "OPERATOR"})
    assert result["recovered_item_value"] == "500.00"
    assert result["net_recovery"] == "500.00"


def test_supplier_credit_is_not_assumed_to_equal_cost():
    result = financial_preview({
        "cogs": "1000", "supplier_credit": "325", "refund": "0",
        "return_shipping": "0", "handling": "0", "payment_fee": "0",
        "write_off": "0", "disposition": "RETURN_TO_SUPPLIER"
    }, {"role": "ACCOUNTANT"})
    assert result["recovered_item_value"] == "325.00"


def test_fisher_exact_is_two_sided_and_bounded():
    from app.financial_lifecycle import fisher_exact_two_sided
    p = fisher_exact_two_sided(1, 9, 11, 3)
    assert 0 <= p <= 1
    assert round(p, 6) == 0.002759
