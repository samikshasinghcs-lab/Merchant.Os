"""Inventory exposure, reorder point, and safety-stock estimators."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True, slots=True)
class InventoryPolicy:
    reorder_point: float
    safety_stock: float
    average_lead_time_demand: float
    service_factor: float

class InventoryPlanner:
    SERVICE_FACTORS={.90:1.2816,.95:1.6449,.975:1.96,.99:2.3263,.995:2.5758}
    def policy(self,average_daily_demand: float,demand_stddev: float,lead_time_days: float,service_level: float=.95,lead_time_stddev: float=0.0) -> InventoryPolicy:
        if min(average_daily_demand,demand_stddev,lead_time_days,lead_time_stddev)<0: raise ValueError("inputs must be non-negative")
        if service_level not in self.SERVICE_FACTORS: raise ValueError("unsupported service level")
        z=self.SERVICE_FACTORS[service_level]
        demand_during=sqrt(lead_time_days*demand_stddev**2+average_daily_demand**2*lead_time_stddev**2)
        safety=z*demand_during; mean_demand=average_daily_demand*lead_time_days
        return InventoryPolicy(mean_demand+safety,safety,mean_demand,z)
    def economic_order_quantity(self,annual_demand: float,order_cost: float,holding_cost_per_unit: float) -> float|None:
        if min(annual_demand,order_cost,holding_cost_per_unit)<0: raise ValueError("inputs must be non-negative")
        if holding_cost_per_unit==0: return None
        return sqrt(2*annual_demand*order_cost/holding_cost_per_unit)
    def days_of_inventory(self,on_hand: float,average_daily_demand: float) -> float|None:
        if on_hand<0 or average_daily_demand<0: raise ValueError("inputs must be non-negative")
        return None if average_daily_demand==0 else on_hand/average_daily_demand
