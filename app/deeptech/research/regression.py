"""Ordinary and ridge linear regression with explicit numerical diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Sequence
from .matrix import ridge_regression
from .statistics import mean

@dataclass(frozen=True, slots=True)
class RegressionFit:
    coefficients: tuple[float,...]
    predictions: tuple[float,...]
    residuals: tuple[float,...]
    r_squared: float
    rmse: float
    sample_size: int
    feature_count: int

class LinearRegression:
    def fit(self,features: Sequence[Sequence[float]],target: Sequence[float],regularization: float=0.0) -> RegressionFit:
        if not features or len(features)!=len(target): raise ValueError("paired training data required")
        if len(features)<=len(features[0])+1: raise ValueError("more observations than parameters required")
        coefficients=ridge_regression(features,target,regularization)
        predictions=tuple(coefficients[0]+sum(c*float(x) for c,x in zip(coefficients[1:],row)) for row in features)
        residuals=tuple(float(y)-p for y,p in zip(target,predictions)); center=mean(target)
        total=sum((float(y)-center)**2 for y in target); error=sum(r*r for r in residuals)
        r2=1-error/total if total else 0.0
        return RegressionFit(coefficients,predictions,residuals,r2,sqrt(error/len(target)),len(target),len(features[0]))
    def predict(self,coefficients: Sequence[float],features: Sequence[Sequence[float]]) -> tuple[float,...]:
        if not coefficients: raise ValueError("coefficients required")
        if any(len(row)!=len(coefficients)-1 for row in features): raise ValueError("feature width mismatch")
        return tuple(coefficients[0]+sum(c*float(x) for c,x in zip(coefficients[1:],row)) for row in features)
