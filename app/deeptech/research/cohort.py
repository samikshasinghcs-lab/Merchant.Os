"""Cohort retention and repeat-purchase analytics."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
from typing import Iterable, Mapping

class CohortAnalyzer:
    def monthly_cohorts(self,rows: Iterable[Mapping],customer_field: str="customer_id",timestamp_field: str="occurred_at") -> dict:
        first={}; activity=defaultdict(set)
        for row in rows:
            customer=str(row[customer_field]); stamp=row[timestamp_field]
            if isinstance(stamp,str): stamp=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if isinstance(stamp,datetime): stamp=stamp.date()
            if not isinstance(stamp,date): raise ValueError("timestamp must be date or datetime")
            month=stamp.year*12+stamp.month-1
            first[customer]=min(first.get(customer,month),month); activity[customer].add(month)
        cohorts=defaultdict(list)
        for customer,month in first.items(): cohorts[month].append(customer)
        result={}
        for cohort,customers in sorted(cohorts.items()):
            periods=defaultdict(set)
            for customer in customers:
                for active in activity[customer]:
                    if active>=cohort: periods[active-cohort].add(customer)
            result[cohort]={"size":len(customers),"retention":{period:len(users)/len(customers) for period,users in sorted(periods.items())}}
        return result
    def repeat_rate(self,orders_by_customer: Mapping[str,int]) -> float:
        if not orders_by_customer: raise ValueError("customer orders required")
        if any(value<0 for value in orders_by_customer.values()): raise ValueError("order counts must be non-negative")
        return sum(value>1 for value in orders_by_customer.values())/len(orders_by_customer)
    def purchase_frequency(self,total_orders: int,unique_customers: int) -> float:
        if total_orders<0 or unique_customers<=0: raise ValueError("invalid order/customer counts")
        return total_orders/unique_customers
