"""Group-level error diagnostics; metrics are descriptive, not legal conclusions."""
from __future__ import annotations
from typing import Iterable, Mapping
from .statistics import mean

class GroupMetrics:
    def summarize(self,labels: Iterable[int],predictions: Iterable[int],groups: Iterable[str]) -> Mapping[str,dict]:
        y=list(map(int,labels)); p=list(map(int,predictions)); g=list(map(str,groups))
        if not y or len(y)!=len(p) or len(y)!=len(g): raise ValueError("equal non-empty arrays required")
        if any(v not in (0,1) for v in y+p): raise ValueError("binary labels and predictions required")
        result={}
        for group in sorted(set(g)):
            indices=[i for i,value in enumerate(g) if value==group]; actual=[y[i] for i in indices]; predicted=[p[i] for i in indices]
            positives=sum(actual); negatives=len(actual)-positives; tp=sum(a==1 and b==1 for a,b in zip(actual,predicted)); fp=sum(a==0 and b==1 for a,b in zip(actual,predicted)); fn=sum(a==1 and b==0 for a,b in zip(actual,predicted))
            result[group]={"count":len(indices),"positive_rate":positives/len(indices),"selection_rate":sum(predicted)/len(indices),"tpr":tp/positives if positives else None,"fpr":fp/negatives if negatives else None,"false_negative_rate":fn/positives if positives else None}
        return result
    def max_gap(self,metrics: Mapping[str,dict],field: str) -> float|None:
        values=[row[field] for row in metrics.values() if row.get(field) is not None]
        return max(values)-min(values) if len(values)>=2 else None
    def report(self,metrics: Mapping[str,dict]) -> dict:
        fields=("selection_rate","tpr","fpr"); return {field:self.max_gap(metrics,field) for field in fields}
