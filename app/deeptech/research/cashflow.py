"""Cash-flow projection and liquidity runway diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence
from .money import decimal_value

@dataclass(frozen=True, slots=True)
class CashFlowPeriod:
    label: str
    inflows: Decimal
    outflows: Decimal
    opening_cash: Decimal
    closing_cash: Decimal
    def __post_init__(self):
        for field in ("inflows","outflows","opening_cash","closing_cash"):
            value=decimal_value(getattr(self,field)); object.__setattr__(self,field,value)
        if self.inflows<0 or self.outflows<0: raise ValueError("inflows and outflows must be non-negative")
        if self.closing_cash!=self.opening_cash+self.inflows-self.outflows: raise ValueError("closing cash does not reconcile")

class CashFlowProjector:
    def project(self,opening_cash: Decimal,inflows: Sequence[Decimal],outflows: Sequence[Decimal],labels: Sequence[str]|None=None) -> tuple[CashFlowPeriod,...]:
        if len(inflows)!=len(outflows) or not inflows: raise ValueError("paired non-empty cash flows required")
        names=list(labels or [str(i+1) for i in range(len(inflows))])
        if len(names)!=len(inflows): raise ValueError("labels length mismatch")
        balance=decimal_value(opening_cash); rows=[]
        for name,inc,out in zip(names,inflows,outflows):
            inc=decimal_value(inc); out=decimal_value(out); close=balance+inc-out
            rows.append(CashFlowPeriod(name,inc,out,balance,close)); balance=close
        return tuple(rows)
    def runway_periods(self,opening_cash: Decimal,net_burn_per_period: Decimal) -> float|None:
        cash=decimal_value(opening_cash); burn=decimal_value(net_burn_per_period)
        if burn<=0: return None
        if cash<=0: return 0.0
        return float(cash/burn)
    def minimum_cash(self,periods: Sequence[CashFlowPeriod]) -> Decimal:
        if not periods: raise ValueError("periods required")
        return min(row.closing_cash for row in periods)
    def liquidity_breach(self,periods: Sequence[CashFlowPeriod],minimum: Decimal) -> tuple[str,...]:
        threshold=decimal_value(minimum)
        return tuple(row.label for row in periods if row.closing_cash<threshold)
