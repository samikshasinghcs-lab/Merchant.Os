from datetime import datetime, timedelta, timezone

import pytest

from app.deeptech.research.temporal_validation import (
    PurgedWalkForwardSplitter,
    assert_no_temporal_leakage,
    audit_feature_availability,
    label_maturity_cutoff,
    matured_training_indices,
    validate_fold_integrity,
)

BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def times(count):
    return [BASE + timedelta(days=index) for index in range(count)]


def test_walk_forward_folds_are_ordered_and_disjoint():
    folds = PurgedWalkForwardSplitter().split(times(20), 5, 3, 3, timedelta(days=1))
    assert len(folds) == 3
    for fold in folds:
        validate_fold_integrity(fold, 20)
        assert max(fold.train_indices) < min(fold.test_indices)


def test_embargo_removes_boundary_rows():
    fold = PurgedWalkForwardSplitter().split(times(12), 3, 2, 2, timedelta(days=2))[0]
    assert fold.train_cutoff == fold.test_start - timedelta(days=2)
    assert times(12)[fold.train_indices[-1]] < fold.train_cutoff


def test_unsorted_timestamps_fail():
    values = times(10)
    values[3], values[4] = values[4], values[3]
    with pytest.raises(ValueError):
        PurgedWalkForwardSplitter().split(values, 2, 2, 2)


def test_feature_availability_audit_detects_future_information():
    events = times(2)
    availability = [events[0], events[1] + timedelta(hours=1)]
    audit = audit_feature_availability(events, availability)
    assert not audit.passed
    assert audit.findings[0].code == "FUTURE_FEATURE"
    with pytest.raises(ValueError):
        assert_no_temporal_leakage(audit)


def test_label_availability_is_audited_separately():
    events = times(2)
    labels = [events[0] + timedelta(days=7), events[1]]
    audit = audit_feature_availability(events, events, labels)
    assert [finding.code for finding in audit.findings] == ["FUTURE_LABEL"]


def test_matured_training_rows_only_include_available_labels():
    events = times(3)
    labels = [events[0] + timedelta(days=1), events[1] + timedelta(days=3), events[2]]
    assert matured_training_indices(events, labels, BASE + timedelta(days=2)) == (0, 2)


def test_label_maturity_cutoff_accounts_for_reporting_delay():
    result = label_maturity_cutoff(BASE, timedelta(days=30), timedelta(days=2))
    assert result == BASE + timedelta(days=32)


def test_fold_validation_rejects_out_of_range_indices():
    fold = PurgedWalkForwardSplitter().split(times(10), 3, 2, 2)[0]
    with pytest.raises(IndexError):
        validate_fold_integrity(fold, 2)
