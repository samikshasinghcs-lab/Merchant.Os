"""Repeatable microbenchmark harness with warmups and percentile summaries."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from time import perf_counter
from typing import Callable, Any

@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    iterations: int
    median_seconds: float
    p95_seconds: float
    minimum_seconds: float
    maximum_seconds: float
    operations_per_second: float

class BenchmarkRunner:
    def run(self,name: str,operation: Callable[[],Any],iterations: int=100,warmups: int=5) -> BenchmarkResult:
        if not name or iterations<1 or warmups<0: raise ValueError("invalid benchmark configuration")
        for _ in range(warmups): operation()
        durations=[]
        for _ in range(iterations):
            start=perf_counter(); operation(); durations.append(perf_counter()-start)
        ordered=sorted(durations); p95=ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))]; med=median(durations)
        return BenchmarkResult(name,iterations,med,p95,min(durations),max(durations),0.0 if med==0 else 1/med)
    def compare(self,baseline: BenchmarkResult,candidate: BenchmarkResult) -> dict:
        ratio=None if baseline.median_seconds==0 else candidate.median_seconds/baseline.median_seconds
        return {"baseline":baseline.name,"candidate":candidate.name,"latency_ratio":ratio,"candidate_faster":None if ratio is None else ratio<1,"warning":"microbenchmarks are environment-sensitive; repeat on representative hardware"}
