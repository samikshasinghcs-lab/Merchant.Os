"""Explainable robust anomaly detection with merchant-local baselines."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from datetime import date
from statistics import median
from typing import Iterable
from .models import Transaction, AnomalyFinding
from .statistics import robust_z_score, quantile, mean, population_std

@dataclass(frozen=True, slots=True)
class AnomalyConfig:
    minimum_baseline: int = 8
    amount_z_threshold: float = 4.0
    velocity_z_threshold: float = 3.5
    high_value_quantile: float = 0.995
    high_value_floor: float = 5.0
    score_cap: float = 100.0

    def __post_init__(self):
        if self.minimum_baseline < 3:
            raise ValueError("minimum_baseline must be at least 3")
        if self.amount_z_threshold <= 0 or self.velocity_z_threshold <= 0:
            raise ValueError("z thresholds must be positive")
        if not 0.5 < self.high_value_quantile < 1:
            raise ValueError("high_value_quantile must be between .5 and 1")

class RobustAnomalyDetector:
    """A transparent rules+robust-statistics detector, not a trained fraud model.

    Baselines are isolated by merchant and currency. A transaction is compared
    only with earlier observations supplied to `fit`; callers must enforce their
    own tenant authorization before constructing the dataset.
    """
    def __init__(self, config: AnomalyConfig | None = None):
        self.config = config or AnomalyConfig()
        self._amounts: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._daily_counts: dict[tuple[str, str, date], int] = defaultdict(int)
        self._fitted = False

    def fit(self, transactions: Iterable[Transaction]) -> "RobustAnomalyDetector":
        self._amounts.clear(); self._daily_counts.clear()
        ordered = sorted(transactions, key=lambda tx: tx.occurred_at)
        for tx in ordered:
            key = (tx.merchant_id, tx.currency)
            self._amounts[key].append(float(tx.amount))
            self._daily_counts[(tx.merchant_id, tx.currency, tx.occurred_at.date())] += 1
        self._fitted = True
        return self

    def score_one(self, tx: Transaction) -> AnomalyFinding:
        if not self._fitted:
            raise RuntimeError("fit must be called before score_one")
        key = (tx.merchant_id, tx.currency)
        baseline = self._amounts.get(key, [])
        signals: list[str] = []
        amount_z = robust_z_score(float(tx.amount), baseline) if len(baseline) >= self.config.minimum_baseline else 0.0
        if abs(amount_z) >= self.config.amount_z_threshold:
            signals.append("AMOUNT_DEVIATION_FROM_MERCHANT_BASELINE")
        high_value = quantile(baseline, self.config.high_value_quantile) if len(baseline) >= self.config.minimum_baseline else self.config.high_value_floor
        if float(tx.amount) >= max(high_value, self.config.high_value_floor):
            signals.append("AMOUNT_ABOVE_MERCHANT_TAIL_THRESHOLD")
        # Fit data is treated as historical. Compare to the same weekday-free daily average.
        day_counts = [count for (merchant, currency, _), count in self._daily_counts.items() if (merchant, currency) == key]
        daily_mean = mean(day_counts)
        velocity_ratio = (self._daily_counts.get((tx.merchant_id, tx.currency, tx.occurred_at.date()), 0) + 1) / daily_mean if daily_mean else 0.0
        velocity_scale = population_std(day_counts) / daily_mean if len(day_counts) > 1 and daily_mean else 1.0
        velocity_z = (velocity_ratio - 1.0) / max(velocity_scale, 1e-9)
        if len(day_counts) >= self.config.minimum_baseline and velocity_z >= self.config.velocity_z_threshold:
            signals.append("DAILY_VELOCITY_ELEVATION")
        score = min(self.config.score_cap, abs(amount_z) * 12 + max(0.0, velocity_z) * 8 + (15 if "AMOUNT_ABOVE_MERCHANT_TAIL_THRESHOLD" in signals else 0))
        severity = "CRITICAL" if score >= 75 else "HIGH" if score >= 50 else "MEDIUM" if score >= 25 else "LOW"
        return AnomalyFinding(
            transaction_id=tx.transaction_id, score=round(score, 4), severity=severity,
            signals=tuple(signals), baseline={"sample_size": float(len(baseline)), "amount_median": float(median(baseline)) if baseline else 0.0, "amount_p995": high_value, "daily_count_mean": daily_mean},
            observed={"amount": float(tx.amount), "amount_robust_z": amount_z, "daily_velocity_ratio": velocity_ratio, "velocity_z": velocity_z},
        )

    def score(self, transactions: Iterable[Transaction]) -> list[AnomalyFinding]:
        return [self.score_one(tx) for tx in transactions]
