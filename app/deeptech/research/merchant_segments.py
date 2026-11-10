"""Transparent rule-based merchant segmentation and lifecycle classification."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True, slots=True)
class MerchantProfile:
    merchant_id: str
    monthly_gmv: float
    order_count: int
    refund_rate: float
    dispute_rate: float
    active_days: int
    @classmethod
    def from_mapping(cls,row: Mapping):
        result=cls(str(row["merchant_id"]),float(row["monthly_gmv"]),int(row["order_count"]),float(row["refund_rate"]),float(row["dispute_rate"]),int(row["active_days"]))
        if result.monthly_gmv<0 or result.order_count<0 or result.active_days<0 or not 0<=result.refund_rate<=1 or not 0<=result.dispute_rate<=1: raise ValueError("invalid merchant profile")
        return result

class MerchantSegmenter:
    def classify(self,profile: MerchantProfile) -> dict:
        if profile.active_days<30: lifecycle="new"
        elif profile.order_count==0: lifecycle="inactive"
        elif profile.active_days>=180: lifecycle="established"
        else: lifecycle="growing"
        scale="enterprise" if profile.monthly_gmv>=1_000_000 else "mid_market" if profile.monthly_gmv>=100_000 else "small_business"
        risk="elevated" if profile.dispute_rate>=.03 or profile.refund_rate>=.15 else "watch" if profile.dispute_rate>=.015 or profile.refund_rate>=.08 else "normal"
        return {"merchant_id":profile.merchant_id,"lifecycle":lifecycle,"scale":scale,"operational_risk_segment":risk,"rules_version":"1.0","disclaimer":"descriptive segmentation, not underwriting or eligibility"}
    def batch(self,profiles): return tuple(self.classify(profile) for profile in profiles)
