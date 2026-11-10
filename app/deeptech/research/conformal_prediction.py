"""Distribution-light conformal intervals for calibrated risk and exposure models.

The routines here implement split conformal prediction. They provide marginal
coverage under exchangeability; they do not promise conditional coverage for
every merchant, product, geography, or time period. Calibration data must be
kept separate from model fitting data and should resemble the deployment
population. The module is dependency-free and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class PredictionInterval:
    """A finite interval and the calibration context that produced it."""

    lower: float
    upper: float
    confidence: float
    radius: float
    calibration_size: int
    method: str = "split_conformal_absolute_residual"

    def __post_init__(self) -> None:
        values = (self.lower, self.upper, self.confidence, self.radius)
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("interval values must be finite")
        if self.lower > self.upper:
            raise ValueError("lower bound cannot exceed upper bound")
        if not 0 < self.confidence < 1:
            raise ValueError("confidence must be between zero and one")
        if self.radius < 0 or self.calibration_size < 1:
            raise ValueError("invalid calibration metadata")

    @property
    def width(self) -> float:
        return self.upper - self.lower

    def contains(self, value: float) -> bool:
        candidate = float(value)
        if not isfinite(candidate):
            raise ValueError("candidate must be finite")
        return self.lower <= candidate <= self.upper


@dataclass(frozen=True, slots=True)
class CoverageReport:
    count: int
    covered: int
    empirical_coverage: float
    mean_width: float
    nominal_coverage: float
    undercoverage: float


def _finite(values: Iterable[float], label: str) -> list[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{label} cannot be empty")
    if any(not isfinite(value) for value in result):
        raise ValueError(f"{label} must be finite")
    return result


def finite_sample_quantile(scores: Sequence[float], confidence: float) -> float:
    """Return the conservative finite-sample conformal order statistic.

    Uses rank ceil((n + 1) * confidence), clipped to n. This is deliberately
    not an interpolated percentile: interpolation can destroy the finite
    sample coverage guarantee.
    """
    values = sorted(_finite(scores, "scores"))
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    rank = min(len(values), int((len(values) + 1) * confidence + 0.999999999))
    return values[max(0, rank - 1)]


class SplitConformalRegressor:
    """Wrap a point predictor with an absolute-residual conformal interval.

    The predictor is a callable accepting one feature row. The wrapper never
    fits or mutates the predictor; callers own model training and data splits.
    """

    def __init__(self, predictor: Callable[[Mapping[str, float]], float], confidence: float = 0.9):
        if not callable(predictor):
            raise TypeError("predictor must be callable")
        if not 0 < confidence < 1:
            raise ValueError("confidence must be between zero and one")
        self.predictor = predictor
        self.confidence = float(confidence)
        self.radius: float | None = None
        self.calibration_size = 0

    def calibrate(
        self,
        rows: Sequence[Mapping[str, float]],
        targets: Sequence[float],
    ) -> "SplitConformalRegressor":
        if len(rows) != len(targets) or not rows:
            raise ValueError("calibration rows and targets must be equally sized and non-empty")
        residuals: list[float] = []
        for row, target in zip(rows, targets):
            observed = float(target)
            predicted = float(self.predictor(row))
            if not isfinite(observed) or not isfinite(predicted):
                raise ValueError("calibration values must be finite")
            residuals.append(abs(observed - predicted))
        self.radius = finite_sample_quantile(residuals, self.confidence)
        self.calibration_size = len(residuals)
        return self

    def predict_interval(self, row: Mapping[str, float]) -> PredictionInterval:
        if self.radius is None:
            raise RuntimeError("calibrator must be fitted before prediction")
        point = float(self.predictor(row))
        if not isfinite(point):
            raise ValueError("predictor returned a non-finite value")
        return PredictionInterval(
            lower=point - self.radius,
            upper=point + self.radius,
            confidence=self.confidence,
            radius=self.radius,
            calibration_size=self.calibration_size,
        )

    def predict_many(self, rows: Sequence[Mapping[str, float]]) -> tuple[PredictionInterval, ...]:
        return tuple(self.predict_interval(row) for row in rows)


def evaluate_coverage(
    intervals: Sequence[PredictionInterval],
    targets: Sequence[float],
) -> CoverageReport:
    if len(intervals) != len(targets) or not intervals:
        raise ValueError("intervals and targets must be equally sized and non-empty")
    observed = _finite(targets, "targets")
    covered = sum(interval.contains(value) for interval, value in zip(intervals, observed))
    nominal_values = {round(interval.confidence, 12) for interval in intervals}
    if len(nominal_values) != 1:
        raise ValueError("all intervals must use the same nominal confidence")
    nominal = intervals[0].confidence
    empirical = covered / len(intervals)
    width = sum(interval.width for interval in intervals) / len(intervals)
    return CoverageReport(
        count=len(intervals),
        covered=covered,
        empirical_coverage=empirical,
        mean_width=width,
        nominal_coverage=nominal,
        undercoverage=max(0.0, nominal - empirical),
    )


class GroupwiseConformalCalibrator:
    """Maintain independent residual calibrators for explicitly named groups.

    Groupwise calibration can improve heterogeneity handling but small groups
    produce unstable estimates. A minimum sample threshold is enforced and
    unseen/undersized groups fail closed rather than silently borrowing a
    misleading global interval.
    """

    def __init__(self, confidence: float = 0.9, minimum_group_size: int = 30):
        if not 0 < confidence < 1 or minimum_group_size < 1:
            raise ValueError("invalid group calibration configuration")
        self.confidence = confidence
        self.minimum_group_size = minimum_group_size
        self._radii: dict[str, tuple[float, int]] = {}

    def fit(
        self,
        groups: Sequence[str],
        predictions: Sequence[float],
        targets: Sequence[float],
    ) -> "GroupwiseConformalCalibrator":
        if not groups or not (len(groups) == len(predictions) == len(targets)):
            raise ValueError("group, prediction, and target arrays must align")
        buckets: dict[str, list[float]] = {}
        for group, prediction, target in zip(groups, predictions, targets):
            key = str(group).strip()
            if not key:
                raise ValueError("group key cannot be empty")
            p, y = float(prediction), float(target)
            if not isfinite(p) or not isfinite(y):
                raise ValueError("predictions and targets must be finite")
            buckets.setdefault(key, []).append(abs(y - p))
        fitted: dict[str, tuple[float, int]] = {}
        for key, residuals in buckets.items():
            if len(residuals) >= self.minimum_group_size:
                fitted[key] = (finite_sample_quantile(residuals, self.confidence), len(residuals))
        self._radii = fitted
        return self

    def interval(self, group: str, prediction: float) -> PredictionInterval:
        key = str(group).strip()
        if key not in self._radii:
            raise KeyError("group is unknown or has insufficient calibration observations")
        point = float(prediction)
        if not isfinite(point):
            raise ValueError("prediction must be finite")
        radius, size = self._radii[key]
        return PredictionInterval(point - radius, point + radius, self.confidence, radius, size)

    @property
    def calibrated_groups(self) -> tuple[str, ...]:
        return tuple(sorted(self._radii))

    def calibration_summary(self) -> dict[str, dict[str, float | int]]:
        return {
            key: {"radius": radius, "sample_size": size}
            for key, (radius, size) in sorted(self._radii.items())
        }
