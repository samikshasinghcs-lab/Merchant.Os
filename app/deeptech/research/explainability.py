"""Deterministic, model-agnostic explanations for tabular risk models.

These methods explain model behaviour, not real-world causality. Permutation
importance measures predictive reliance under a chosen evaluation sample;
correlated features can share or mask importance. Additive linear explanations
are exact only for the supplied coefficient representation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from random import Random
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class FeatureContribution:
    feature: str
    contribution: float
    direction: str
    baseline: float
    value: float


@dataclass(frozen=True, slots=True)
class Explanation:
    prediction: float
    baseline: float
    contributions: tuple[FeatureContribution, ...]
    method: str

    @property
    def reconstruction_error(self) -> float:
        reconstructed = self.baseline + sum(item.contribution for item in self.contributions)
        return self.prediction - reconstructed


@dataclass(frozen=True, slots=True)
class ImportanceResult:
    feature: str
    baseline_score: float
    permuted_scores: tuple[float, ...]
    mean_score_drop: float
    standard_deviation: float
    repeats: int


def _number(value: float, label: str) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def explain_linear_prediction(
    row: Mapping[str, float],
    coefficients: Mapping[str, float],
    intercept: float = 0.0,
    baseline_values: Mapping[str, float] | None = None,
) -> Explanation:
    """Decompose a linear prediction into exact feature contributions."""
    if not coefficients:
        raise ValueError("coefficients cannot be empty")
    if set(row) != set(coefficients):
        raise ValueError("row and coefficient schemas must match exactly")
    baseline = dict(baseline_values or {key: 0.0 for key in coefficients})
    if set(baseline) != set(coefficients):
        raise ValueError("baseline schema must match coefficients")
    base_prediction = _number(intercept, "intercept") + sum(
        _number(coefficients[key], "coefficient") * _number(baseline[key], "baseline")
        for key in coefficients
    )
    contributions: list[FeatureContribution] = []
    for key in sorted(coefficients):
        value = _number(row[key], "feature value")
        reference = _number(baseline[key], "baseline value")
        coefficient = _number(coefficients[key], "coefficient")
        contribution = coefficient * (value - reference)
        direction = "increases" if contribution > 0 else "decreases" if contribution < 0 else "neutral"
        contributions.append(FeatureContribution(key, contribution, direction, reference, value))
    prediction = _number(intercept, "intercept") + sum(
        _number(coefficients[key], "coefficient") * _number(row[key], "feature value")
        for key in coefficients
    )
    return Explanation(prediction, base_prediction, tuple(contributions), "exact_linear_decomposition")


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    return sum(values) / len(values)


def _score_predictions(
    actual: Sequence[float], predicted: Sequence[float], metric: str,
) -> float:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted arrays must align and be non-empty")
    pairs = [(_number(a, "actual"), _number(p, "prediction")) for a, p in zip(actual, predicted)]
    if metric == "mae":
        return _mean([abs(a - p) for a, p in pairs])
    if metric == "rmse":
        return (_mean([(a - p) ** 2 for a, p in pairs])) ** 0.5
    if metric == "accuracy":
        return sum(round(p) == round(a) for a, p in pairs) / len(pairs)
    raise ValueError("metric must be one of: mae, rmse, accuracy")


class PermutationImportance:
    """Estimate feature reliance by deterministic column permutation."""

    def __init__(self, repeats: int = 10, seed: int = 17, metric: str = "mae"):
        if repeats < 2:
            raise ValueError("at least two permutation repeats are required")
        if metric not in {"mae", "rmse", "accuracy"}:
            raise ValueError("unsupported metric")
        self.repeats = repeats
        self.seed = seed
        self.metric = metric

    def evaluate(
        self,
        rows: Sequence[Mapping[str, float]],
        targets: Sequence[float],
        predictor: Callable[[Mapping[str, float]], float],
    ) -> tuple[ImportanceResult, ...]:
        if not rows or len(rows) != len(targets):
            raise ValueError("rows and targets must align and be non-empty")
        keys = tuple(sorted(rows[0]))
        if not keys or any(set(row) != set(keys) for row in rows):
            raise ValueError("all rows must share a non-empty feature schema")
        actual = [_number(value, "target") for value in targets]
        baseline_predictions = [_number(predictor(row), "prediction") for row in rows]
        baseline_score = _score_predictions(actual, baseline_predictions, self.metric)
        results: list[ImportanceResult] = []
        for feature_index, feature in enumerate(keys):
            scores: list[float] = []
            for repeat in range(self.repeats):
                rng = Random(self.seed + feature_index * 100_003 + repeat)
                permuted_values = [row[feature] for row in rows]
                rng.shuffle(permuted_values)
                altered = [dict(row) for row in rows]
                for row, value in zip(altered, permuted_values):
                    row[feature] = value
                predictions = [_number(predictor(row), "prediction") for row in altered]
                scores.append(_score_predictions(actual, predictions, self.metric))
            mean_score = _mean(scores)
            variance = _mean([(score - mean_score) ** 2 for score in scores])
            # For error metrics, a positive drop means permutation worsened
            # performance. For accuracy, invert the sign for the same meaning.
            drop = mean_score - baseline_score
            if self.metric == "accuracy":
                drop = baseline_score - mean_score
            results.append(ImportanceResult(
                feature, baseline_score, tuple(scores), drop, variance ** 0.5, self.repeats,
            ))
        return tuple(sorted(results, key=lambda item: (-item.mean_score_drop, item.feature)))


def top_contributors(explanation: Explanation, limit: int = 5) -> tuple[FeatureContribution, ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    return tuple(sorted(
        explanation.contributions,
        key=lambda item: (-abs(item.contribution), item.feature),
    )[:limit])


def explanation_to_dict(explanation: Explanation, precision: int = 8) -> dict:
    """Produce a stable, JSON-friendly representation for audit records."""
    if precision < 0 or precision > 15:
        raise ValueError("precision must be between 0 and 15")
    return {
        "method": explanation.method,
        "prediction": round(explanation.prediction, precision),
        "baseline": round(explanation.baseline, precision),
        "reconstruction_error": round(explanation.reconstruction_error, precision),
        "contributions": [
            {
                "feature": item.feature,
                "contribution": round(item.contribution, precision),
                "direction": item.direction,
                "baseline_value": round(item.baseline, precision),
                "observed_value": round(item.value, precision),
            }
            for item in explanation.contributions
        ],
    }
