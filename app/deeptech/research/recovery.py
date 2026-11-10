"""Recovery and retry policy helpers for asynchronous provider workflows."""
from __future__ import annotations
from dataclasses import dataclass
from math import pow
from random import Random

@dataclass(frozen=True, slots=True)
class RetryDecision:
    allowed: bool
    delay_seconds: float
    attempt: int
    reason: str

class RetryPolicy:
    def __init__(self,max_attempts: int=5,base_delay: float=1.0,max_delay: float=300.0,multiplier: float=2.0,jitter: float=.2):
        if max_attempts<1 or base_delay<0 or max_delay<base_delay or multiplier<1 or not 0<=jitter<=1: raise ValueError("invalid retry policy")
        self.max_attempts=max_attempts; self.base_delay=base_delay; self.max_delay=max_delay; self.multiplier=multiplier; self.jitter=jitter
    def decide(self,attempt: int,retryable: bool,seed: int=1) -> RetryDecision:
        if attempt<1: raise ValueError("attempt numbers start at one")
        if not retryable: return RetryDecision(False,0,attempt,"failure is not retryable")
        if attempt>=self.max_attempts: return RetryDecision(False,0,attempt,"maximum attempts reached")
        delay=min(self.max_delay,self.base_delay*pow(self.multiplier,attempt-1)); rng=Random(seed); delay*=1+self.jitter*(2*rng.random()-1)
        return RetryDecision(True,max(0,delay),attempt,"retryable failure within configured attempt budget")
    def classify_http(self,status_code: int) -> bool:
        if status_code in {408,425,429,500,502,503,504}: return True
        return False
