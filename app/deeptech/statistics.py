"""Dependency-free robust statistics used by the intelligence layer."""
from __future__ import annotations
from math import sqrt, isfinite
from statistics import median
from typing import Iterable, Sequence

def finite_values(values: Iterable[float]) -> list[float]:
    return [float(v) for v in values if isfinite(float(v))]

def quantile(values: Sequence[float], q: float) -> float:
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    data = sorted(finite_values(values))
    if not data:
        raise ValueError("quantile requires at least one finite value")
    position = (len(data) - 1) * q
    low = int(position); high = min(low + 1, len(data) - 1)
    fraction = position - low
    return data[low] * (1 - fraction) + data[high] * fraction

def median_absolute_deviation(values: Sequence[float], center: float | None = None) -> float:
    data = finite_values(values)
    if not data:
        raise ValueError("MAD requires at least one finite value")
    c = median(data) if center is None else float(center)
    return float(median([abs(x - c) for x in data]))

def robust_z_score(value: float, values: Sequence[float], epsilon: float = 1e-9) -> float:
    data = finite_values(values)
    if not data:
        return 0.0
    center = float(median(data))
    mad = median_absolute_deviation(data, center)
    if mad <= epsilon:
        # If the baseline is constant, any material deviation is informative.
        return 0.0 if abs(value - center) <= epsilon else (float("inf") if value > center else float("-inf"))
    return 0.6744897501960817 * (float(value) - center) / mad

def mean(values: Sequence[float]) -> float:
    data = finite_values(values)
    return sum(data) / len(data) if data else 0.0

def population_std(values: Sequence[float]) -> float:
    data = finite_values(values)
    if not data:
        return 0.0
    m = mean(data)
    return sqrt(sum((x - m) ** 2 for x in data) / len(data))

def ewma(values: Sequence[float], alpha: float = 0.2, initial: float | None = None) -> list[float]:
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    data = finite_values(values)
    if not data:
        return []
    result = []
    state = data[0] if initial is None else float(initial)
    for value in data:
        state = alpha * value + (1 - alpha) * state
        result.append(state)
    return result

def cusum(values: Sequence[float], target: float | None = None, threshold: float = 5.0, drift: float = 0.5) -> list[tuple[int, float, float]]:
    """Two-sided cumulative-sum change detector; returns (index, positive, negative)."""
    if threshold <= 0 or drift < 0:
        raise ValueError("threshold must be positive and drift non-negative")
    data = finite_values(values)
    if not data:
        return []
    center = mean(data) if target is None else float(target)
    scale = population_std(data) or 1.0
    pos = neg = 0.0
    events = []
    for index, value in enumerate(data):
        z = (value - center) / scale
        pos = max(0.0, pos + z - drift)
        neg = min(0.0, neg + z + drift)
        if pos >= threshold or abs(neg) >= threshold:
            events.append((index, pos, neg))
            pos = neg = 0.0
    return events
