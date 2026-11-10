"""Unit economics, contribution margin, and break-even analysis."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .money import decimal_value

@dataclass(frozen=True, slots=True)
class UnitEconomics:
    selling_price: Decimal
    variable_cost: Decimal
    payment_fee: Decimal
    fulfillment_cost: Decimal
    contribution: Decimal
    contribution_margin: float
    def __post_init__(self):
        for field in ("selling_price","variable_cost","payment_fee","fulfillment_cost","contribution"):
            object.__setattr__(self,field,decimal_value(getattr(self,field)))
        if self.selling_price<=0: raise ValueError("selling price must be positive")
        if min(self.variable_cost,self.payment_fee,self.fulfillment_cost)<0: raise ValueError("costs must be non-negative")

class UnitEconomicsCalculator:
    def calculate(self,price: Decimal,variable_cost: Decimal,fee_rate: float,fulfillment: Decimal=Decimal("0")) -> UnitEconomics:
        p=decimal_value(price); v=decimal_value(variable_cost); f=decimal_value(fulfillment)
        if p<=0 or v<0 or f<0 or not 0<=fee_rate<=1: raise ValueError("invalid unit economics inputs")
        fee=p*Decimal(str(fee_rate)); contribution=p-v-fee-f
        return UnitEconomics(p,v,fee,f,contribution,float(contribution/p))
    def break_even_units(self,fixed_cost: Decimal,contribution_per_unit: Decimal) -> int|None:
        fixed=decimal_value(fixed_cost); contribution=decimal_value(contribution_per_unit)
        if fixed<0: raise ValueError("fixed cost cannot be negative")
        if contribution<=0: return None
        from decimal import ROUND_CEILING
        return int((fixed/contribution).to_integral_value(rounding=ROUND_CEILING))
    def target_units(self,fixed_cost: Decimal,target_profit: Decimal,contribution: Decimal) -> int|None:
        return self.break_even_units(decimal_value(fixed_cost)+decimal_value(target_profit),contribution)
    def margin_of_safety(self,actual_sales: Decimal,break_even_sales: Decimal) -> float:
        actual=decimal_value(actual_sales); threshold=decimal_value(break_even_sales)
        if actual==0: raise ValueError("actual sales cannot be zero")
        return float((actual-threshold)/actual)
