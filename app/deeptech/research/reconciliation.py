"""Deterministic provider-to-internal reconciliation and exception classification."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping
from .money import decimal_value

@dataclass(frozen=True, slots=True)
class FinancialRecord:
    record_id: str
    tenant_id: str
    provider_reference: str
    amount: Decimal
    currency: str
    status: str
    def __post_init__(self) -> None:
        if not self.record_id or not self.tenant_id: raise ValueError("record identity required")
        value=decimal_value(self.amount)
        if value<0: raise ValueError("amount cannot be negative")
        object.__setattr__(self,"amount",value); object.__setattr__(self,"currency",self.currency.upper()); object.__setattr__(self,"status",self.status.upper())

@dataclass(frozen=True, slots=True)
class ReconciliationException:
    code: str
    internal_id: str|None
    provider_id: str|None
    explanation: str
    severity: str

@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    matched: tuple[tuple[str,str],...]
    exceptions: tuple[ReconciliationException,...]
    totals_internal: Mapping[str,str]
    totals_provider: Mapping[str,str]

class Reconciler:
    def reconcile(self,tenant_id: str,internal: Iterable[FinancialRecord],provider: Iterable[FinancialRecord]) -> ReconciliationReport:
        left=list(internal); right=list(provider)
        if any(row.tenant_id!=tenant_id for row in left+right): raise PermissionError("cross-tenant reconciliation input")
        if len({r.record_id for r in left})!=len(left) or len({r.record_id for r in right})!=len(right): raise ValueError("duplicate record identifiers")
        lmap={r.provider_reference:r for r in left if r.provider_reference}; rmap={r.provider_reference:r for r in right if r.provider_reference}
        matched=[]; exceptions=[]
        for reference in sorted(set(lmap)|set(rmap)):
            a=lmap.get(reference); b=rmap.get(reference)
            if a is None:
                exceptions.append(ReconciliationException("PROVIDER_ONLY",None,b.record_id,"provider record has no internal match","high")); continue
            if b is None:
                exceptions.append(ReconciliationException("INTERNAL_ONLY",a.record_id,None,"internal record has no provider match","high")); continue
            if a.currency!=b.currency:
                exceptions.append(ReconciliationException("CURRENCY_MISMATCH",a.record_id,b.record_id,"currency codes differ","critical")); continue
            if a.amount!=b.amount:
                exceptions.append(ReconciliationException("AMOUNT_MISMATCH",a.record_id,b.record_id,"amounts differ","critical")); continue
            if a.status!=b.status:
                exceptions.append(ReconciliationException("STATUS_MISMATCH",a.record_id,b.record_id,"statuses differ","high")); continue
            matched.append((a.record_id,b.record_id))
        return ReconciliationReport(tuple(matched),tuple(exceptions),self._totals(left),self._totals(right))
    def _totals(self,rows: list[FinancialRecord]) -> Mapping[str,str]:
        totals={}
        for row in rows: totals[row.currency]=totals.get(row.currency,Decimal(0))+row.amount
        return {k:str(v) for k,v in sorted(totals.items())}
