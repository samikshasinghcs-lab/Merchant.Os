"""Contract and boundary tests for the additional research primitives."""
from datetime import datetime, timedelta, timezone

import pytest

from app.deeptech.research.conformal_prediction import (
    GroupwiseConformalCalibrator,
    SplitConformalRegressor,
    evaluate_coverage,
)
from app.deeptech.research.explainability import (
    PermutationImportance,
    explain_linear_prediction,
)
from app.deeptech.research.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    DeadLetterQueue,
    DeadLetterRecord,
    ExponentialBackoff,
)
from app.deeptech.research.temporal_validation import (
    PurgedWalkForwardSplitter,
    audit_feature_availability,
    matured_training_indices,
)


def test_conformal_interval_width_is_independent_of_prediction_level():
    predictor = lambda row: row["level"]
    model = SplitConformalRegressor(predictor, 0.9)
    rows = [{"level": float(index)} for index in range(40)]
    targets = [row["level"] + (index % 5) for index, row in enumerate(rows)]
    model.calibrate(rows, targets)
    low = model.predict_interval({"level": -1000})
    high = model.predict_interval({"level": 1000})
    assert low.width == high.width
    assert low.radius == high.radius


def test_conformal_calibration_is_deterministic_under_row_reordering():
    predictor = lambda row: row["x"] * 0.25
    rows = [{"x": float(index)} for index in range(25)]
    targets = [predictor(row) + ((index % 4) - 1.5) for index, row in enumerate(rows)]
    first = SplitConformalRegressor(predictor, 0.8).calibrate(rows, targets)
    second = SplitConformalRegressor(predictor, 0.8).calibrate(rows[::-1], targets[::-1])
    assert first.radius == second.radius


def test_group_calibration_does_not_create_global_fallback():
    calibrator = GroupwiseConformalCalibrator(0.9, minimum_group_size=5)
    calibrator.fit(["north"] * 5, [1] * 5, [2] * 5)
    assert calibrator.calibrated_groups == ("north",)
    with pytest.raises(KeyError):
        calibrator.interval("south", 10)


def test_coverage_report_counts_closed_interval_boundaries():
    model = SplitConformalRegressor(lambda row: 0.0, 0.5)
    model.calibrate([{"x": 1}, {"x": 2}, {"x": 3}], [1.0, 2.0, 3.0])
    intervals = model.predict_many([{"x": 4}, {"x": 5}, {"x": 6}])
    report = evaluate_coverage(intervals, [interval.lower for interval in intervals])
    assert report.covered == 3
    assert report.empirical_coverage == 1.0


def test_linear_explanation_sign_matches_coefficient_direction():
    positive = explain_linear_prediction({"feature": 5}, {"feature": 2}, baseline_values={"feature": 1})
    negative = explain_linear_prediction({"feature": 5}, {"feature": -2}, baseline_values={"feature": 1})
    assert positive.contributions[0].direction == "increases"
    assert negative.contributions[0].direction == "decreases"


def test_linear_explanation_has_zero_reconstruction_error_for_many_values():
    coefficients = {"a": 0.125, "b": -3.5, "c": 11.0}
    baseline = {"a": 10.0, "b": 0.0, "c": -2.0}
    for index in range(-20, 21):
        row = {"a": index / 3, "b": index * 2, "c": index - 4}
        explanation = explain_linear_prediction(row, coefficients, 0.375, baseline)
        assert abs(explanation.reconstruction_error) < 1e-10


def test_permutation_importance_reports_zero_drop_for_constant_predictor():
    rows = [{"x": float(index)} for index in range(12)]
    targets = [float(index % 3) for index in range(12)]
    result = PermutationImportance(repeats=3).evaluate(rows, targets, lambda row: 1.0)
    assert len(result) == 1
    assert result[0].mean_score_drop == 0.0


def test_permutation_importance_rejects_inconsistent_feature_schema():
    rows = [{"x": 1.0}, {"y": 2.0}]
    with pytest.raises(ValueError):
        PermutationImportance().evaluate(rows, [1, 2], lambda row: 0.0)


def test_backoff_never_exceeds_configured_cap_for_large_attempt_numbers():
    policy = ExponentialBackoff(0.1, 3.0, maximum_attempts=20)
    for attempt in range(1, 21):
        decision = policy.decide(attempt, 0.5)
        assert decision.allowed
        assert 0 <= decision.delay_seconds <= 3.0
    assert not policy.decide(21).allowed


def test_breaker_success_resets_failure_counter():
    breaker = CircuitBreaker("cache", failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.snapshot().consecutive_failures == 0
    breaker.record_failure()
    assert breaker.snapshot().state.value == "closed"


def test_dead_letter_capacity_evicts_oldest_record_only():
    queue = DeadLetterQueue(capacity=3)
    now = datetime.now(timezone.utc)
    for index in range(3):
        queue.put(DeadLetterRecord(f"e{index}", "tenant", "failed", 1, now, now))
    queue.put(DeadLetterRecord("e3", "tenant", "failed", 1, now, now))
    assert queue.get("tenant", "e0") is None
    assert queue.get("tenant", "e1") is not None
    assert queue.get("tenant", "e3") is not None


def test_dead_letter_update_preserves_first_seen_and_latest_attempts():
    queue = DeadLetterQueue()
    first = datetime(2025, 1, 1, tzinfo=timezone.utc)
    later = first + timedelta(hours=1)
    queue.put(DeadLetterRecord("e", "t", "timeout", 1, first, first))
    queue.put(DeadLetterRecord("e", "t", "timeout", 4, later, later))
    record = queue.get("t", "e")
    assert record.first_seen == first
    assert record.last_seen == later
    assert record.attempts == 4


def test_temporal_split_fold_count_and_test_size_are_exact():
    origin = datetime(2024, 1, 1, tzinfo=timezone.utc)
    stamps = [origin + timedelta(hours=index) for index in range(60)]
    folds = PurgedWalkForwardSplitter().split(stamps, 10, 5, 4)
    assert len(folds) == 4
    assert all(len(fold.test_indices) == 5 for fold in folds)
    assert all(len(fold.train_indices) >= 10 for fold in folds)


def test_temporal_audit_accepts_features_available_at_event_time():
    stamp = datetime(2025, 3, 1, tzinfo=timezone.utc)
    audit = audit_feature_availability([stamp], [stamp], [stamp])
    assert audit.passed
    assert audit.checked_rows == 1


def test_maturity_filter_is_inclusive_at_cutoff():
    stamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    available = [stamp + timedelta(days=1), stamp + timedelta(days=2)]
    assert matured_training_indices([stamp, stamp], available, available[0]) == (0,)


def test_breaker_rejects_naive_clock_values():
    breaker = CircuitBreaker("bad-clock", clock=lambda: datetime(2025, 1, 1))
    with pytest.raises(ValueError):
        breaker.acquire()


def test_conformal_confidence_bounds_are_validated():
    with pytest.raises(ValueError):
        SplitConformalRegressor(lambda row: 0.0, confidence=1.0)
    with pytest.raises(ValueError):
        GroupwiseConformalCalibrator(confidence=0.0)
