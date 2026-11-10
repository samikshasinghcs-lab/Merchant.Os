"""Reproducible microbenchmarks for core analytical primitives."""
from __future__ import annotations
from statistics import mean, median
from time import perf_counter
from typing import Callable, Any

def benchmark_callable(name: str, operation: Callable[[],Any], repetitions: int = 7, warmups: int = 2) -> dict[str,object]:
    if repetitions < 1 or warmups < 0:
        raise ValueError("invalid benchmark repetition counts")
    for _ in range(warmups): operation()
    samples=[]
    for _ in range(repetitions):
        start=perf_counter(); operation(); samples.append((perf_counter()-start)*1000)
    return {"name":name,"repetitions":repetitions,"mean_ms":mean(samples),"median_ms":median(samples),"min_ms":min(samples),"max_ms":max(samples),"samples_ms":samples,"environment_note":"microbenchmark; results depend on hardware, runtime, load and dataset shape"}
