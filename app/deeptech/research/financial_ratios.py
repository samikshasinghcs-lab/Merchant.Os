"""Financial health ratios with denominator and sign validation."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FinancialRatios:
    gross_margin: float|None
    operating_margin: float|None
    net_margin: float|None
    return_on_assets: float|None
    debt_to_assets: float|None
    interest_coverage: float|None

class RatioAnalyzer:
    def calculate(self,revenue: float,cogs: float,operating_income: float,net_income: float,total_assets: float,total_debt: float,interest_expense: float) -> FinancialRatios:
        if revenue<0 or cogs<0 or total_assets<0 or total_debt<0 or interest_expense<0: raise ValueError("invalid financial inputs")
        gross=None if revenue==0 else (revenue-cogs)/revenue
        operating=None if revenue==0 else operating_income/revenue
        net=None if revenue==0 else net_income/revenue
        roa=None if total_assets==0 else net_income/total_assets
        debt=None if total_assets==0 else total_debt/total_assets
        coverage=None if interest_expense==0 else operating_income/interest_expense
        return FinancialRatios(gross,operating,net,roa,debt,coverage)
    def compare(self,left: FinancialRatios,right: FinancialRatios) -> dict:
        result={}
        for field in FinancialRatios.__dataclass_fields__:
            a=getattr(left,field); b=getattr(right,field)
            result[field]={"left":a,"right":b,"delta":None if a is None or b is None else b-a}
        return result
