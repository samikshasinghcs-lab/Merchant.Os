"""Conjugate Bayesian estimators for rates and means with stated priors."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from random import Random
from typing import Iterable

@dataclass(frozen=True, slots=True)
class BetaPosterior:
    alpha: float
    beta: float
    observations: int
    @property
    def mean(self): return self.alpha/(self.alpha+self.beta)
    @property
    def variance(self): return self.alpha*self.beta/((self.alpha+self.beta)**2*(self.alpha+self.beta+1))
    @property
    def mode(self): return (self.alpha-1)/(self.alpha+self.beta-2) if self.alpha>1 and self.beta>1 else None
    def sample(self,rng: Random) -> float: return rng.betavariate(self.alpha,self.beta)
    def interval(self,draws: int=20000,level: float=.95,seed: int=1) -> tuple[float,float]:
        if draws<100 or not 0<level<1: raise ValueError("invalid interval configuration")
        rng=Random(seed); values=sorted(self.sample(rng) for _ in range(draws)); tail=(1-level)/2
        return values[int(tail*(draws-1))],values[int((1-tail)*(draws-1))]

class BetaBinomial:
    def __init__(self,prior_alpha: float=1.0,prior_beta: float=1.0):
        if prior_alpha<=0 or prior_beta<=0: raise ValueError("prior parameters must be positive")
        self.alpha=prior_alpha; self.beta=prior_beta
    def update(self,successes: int,trials: int) -> BetaPosterior:
        if trials<0 or successes<0 or successes>trials: raise ValueError("invalid binomial counts")
        return BetaPosterior(self.alpha+successes,self.beta+trials-successes,trials)
    def sequential(self,observations: Iterable[int]) -> tuple[BetaPosterior,...]:
        alpha=self.alpha; beta=self.beta; results=[]; count=0
        for outcome in observations:
            if outcome not in (0,1): raise ValueError("binary observations required")
            alpha+=outcome; beta+=1-outcome; count+=1; results.append(BetaPosterior(alpha,beta,count))
        return tuple(results)

@dataclass(frozen=True, slots=True)
class NormalPosterior:
    mean: float
    variance: float
    sample_size: int

class NormalKnownVariance:
    def __init__(self,prior_mean: float=0.0,prior_variance: float=100.0,observation_variance: float=1.0):
        if min(prior_variance,observation_variance)<=0: raise ValueError("variances must be positive")
        self.prior_mean=prior_mean; self.prior_variance=prior_variance; self.observation_variance=observation_variance
    def update(self,values: Iterable[float]) -> NormalPosterior:
        data=list(map(float,values)); precision=1/self.prior_variance+len(data)/self.observation_variance
        weighted=self.prior_mean/self.prior_variance+sum(data)/self.observation_variance
        return NormalPosterior(weighted/precision,1/precision,len(data))
