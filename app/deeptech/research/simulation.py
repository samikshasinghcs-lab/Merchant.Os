"""Discrete-event operational simulation for queue and capacity stress testing."""
from __future__ import annotations
from dataclasses import dataclass
from heapq import heappush, heappop
from random import Random
from statistics import mean
from typing import Iterable, Sequence

@dataclass(frozen=True, slots=True)
class QueueSimulationResult:
    arrivals: int
    completed: int
    dropped: int
    mean_wait: float
    p95_wait: float
    utilization: float
    horizon: float
    seed: int

class QueueSimulator:
    """Single-server M/M/1-style discrete-event simulation with finite horizon."""
    def run(self,arrival_rate: float,service_rate: float,horizon: float,seed: int=1,max_queue: int|None=None) -> QueueSimulationResult:
        if arrival_rate<=0 or service_rate<=0 or horizon<=0: raise ValueError("rates and horizon must be positive")
        if max_queue is not None and max_queue<0: raise ValueError("max_queue cannot be negative")
        rng=Random(seed); now=0.0; next_arrival=rng.expovariate(arrival_rate); next_departure=float("inf")
        queue=[]; in_service=None; waits=[]; arrivals=completed=dropped=busy_events=0
        while min(next_arrival,next_departure)<=horizon:
            if next_arrival<=next_departure:
                now=next_arrival; arrivals+=1; next_arrival=now+rng.expovariate(arrival_rate)
                if in_service is None:
                    in_service=now; next_departure=now+rng.expovariate(service_rate); waits.append(0.0)
                elif max_queue is not None and len(queue)>=max_queue: dropped+=1
                else: queue.append(now)
            else:
                now=next_departure; completed+=1
                if queue:
                    arrived=queue.pop(0); waits.append(now-arrived); in_service=now; next_departure=now+rng.expovariate(service_rate)
                else: in_service=None; next_departure=float("inf")
        ordered=sorted(waits)
        p95=ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))] if ordered else 0.0
        return QueueSimulationResult(arrivals,completed,dropped,mean(waits) if waits else 0.0,p95,min(1.0,completed/(service_rate*horizon)),horizon,seed)

@dataclass(frozen=True, slots=True)
class StressScenario:
    name: str
    arrival_multiplier: float
    service_multiplier: float
    duration_multiplier: float=1.0
    def __post_init__(self) -> None:
        if not self.name or min(self.arrival_multiplier,self.service_multiplier,self.duration_multiplier)<=0: raise ValueError("scenario multipliers must be positive")

def run_stress_matrix(simulator: QueueSimulator,base_arrival: float,base_service: float,horizon: float,scenarios: Sequence[StressScenario],seeds: Sequence[int]=(11,23,47)) -> tuple[dict,...]:
    results=[]
    for scenario in scenarios:
        for seed in seeds:
            result=simulator.run(base_arrival*scenario.arrival_multiplier,base_service*scenario.service_multiplier,horizon*scenario.duration_multiplier,seed)
            results.append({"scenario":scenario.name,"seed":seed,"arrivals":result.arrivals,"completed":result.completed,"dropped":result.dropped,"mean_wait":result.mean_wait,"p95_wait":result.p95_wait,"utilization":result.utilization})
    return tuple(results)
