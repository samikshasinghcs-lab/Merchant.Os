"""Refund and dispute exposure estimators with transparent gross/net definitions."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .money import decimal_value

@dataclass(frozen=True, slots=True)
class ExposureEstimate:
    gross_sales: Decimal
    expected_refunds: Decimal
    expected_disputes: Decimal
    variable_cost_at_risk: Decimal
    net_exposure: Decimal
    assumptions: dict

class ExposureEstimator:
    def estimate(self,gross_sales: Decimal,refund_rate: float,dispute_rate: float,variable_cost_rate: float,dispute_fee: Decimal=Decimal("0")) -> ExposureEstimate:
        gross=decimal_value(gross_sales); fee=decimal_value(dispute_fee)
        if gross<0 or fee<0 or any(not 0<=v<=1 for v in (refund_rate,dispute_rate,variable_cost_rate)): raise ValueError("invalid exposure inputs")
        refunds=gross*Decimal(str(refund_rate)); disputes=gross*Decimal(str(dispute_rate)); variable=gross*Decimal(str(variable_cost_rate))
        net=refunds+disputes+fee+variable
        return ExposureEstimate(gross,refunds,disputes,variable,net,{"refund_rate":refund_rate,"dispute_rate":dispute_rate,"variable_cost_rate":variable_cost_rate,"definition":"gross exposure components; not a cash forecast","overlap_assumption":"refund and dispute exposure may overlap"})
    def stress(self,base: ExposureEstimate,refund_multiplier: float=1.0,dispute_multiplier: float=1.0) -> dict:
        if min(refund_multiplier,dispute_multiplier)<0: raise ValueError("multipliers must be non-negative")
        refunds=base.expected_refunds*Decimal(str(refund_multiplier)); disputes=base.expected_disputes*Decimal(str(dispute_multiplier))
        stressed=refunds+disputes+base.variable_cost_at_risk
        return {"refund_exposure":str(refunds),"dispute_exposure":str(disputes),"variable_cost_at_risk":str(base.variable_cost_at_risk),"gross_exposure":str(stressed),"incremental_exposure":str(stressed-base.net_exposure)}
