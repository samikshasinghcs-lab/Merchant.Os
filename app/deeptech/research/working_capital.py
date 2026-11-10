"""Working-capital metrics and cash conversion cycle calculations."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class WorkingCapitalMetrics:
    days_inventory: float
    days_receivable: float
    days_payable: float
    cash_conversion_cycle: float
    current_ratio: float|None
    quick_ratio: float|None

def calculate_working_capital(inventory: float,cogs: float,receivables: float,revenue: float,payables: float,purchases: float,current_assets: float|None=None,current_liabilities: float|None=None,cash: float|None=None) -> WorkingCapitalMetrics:
    if min(inventory,cogs,receivables,revenue,payables,purchases)<0: raise ValueError("inputs must be non-negative")
    if cogs==0 or revenue==0 or purchases==0: raise ValueError("denominators must be positive")
    dio=inventory/cogs*365; dso=receivables/revenue*365; dpo=payables/purchases*365
    current=None; quick=None
    if current_assets is not None or current_liabilities is not None:
        if current_assets is None or current_liabilities is None or current_liabilities<=0: raise ValueError("both current balance values required and liabilities positive")
        current=current_assets/current_liabilities
        if cash is None: raise ValueError("cash required for quick ratio")
        quick=(cash+receivables)/current_liabilities
    return WorkingCapitalMetrics(dio,dso,dpo,dio+dso-dpo,current,quick)

def net_working_capital(current_assets: float,current_liabilities: float) -> float:
    return float(current_assets)-float(current_liabilities)

def operating_cash_ratio(operating_cash_flow: float,current_liabilities: float) -> float:
    if current_liabilities<=0: raise ValueError("current liabilities must be positive")
    return float(operating_cash_flow)/float(current_liabilities)
