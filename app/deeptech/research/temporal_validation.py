"""Leakage-aware temporal validation for merchant and transaction models.

Financial events arrive late, are corrected, and may be backfilled. Random
train/test splits can leak future information into historical evaluation.
These utilities make event time, label availability, and embargo windows
explicit. They intentionally return indices so callers can retain their own
feature matrices without hidden copies or data-frame dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TemporalFold:
    fold: int
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]
    train_cutoff: datetime
    test_start: datetime
    test_end: datetime
    embargo: timedelta

    def __post_init__(self) -> None:
        if self.fold < 0 or not self.train_indices or not self.test_indices:
            raise ValueError("fold requires non-empty train and test indices")
        if set(self.train_indices) & set(self.test_indices):
            raise ValueError("train and test indices overlap")
        if self.train_cutoff > self.test_start:
            raise ValueError("training cutoff cannot follow test start")


@dataclass(frozen=True, slots=True)
class LeakageFinding:
    row_index: int
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class TemporalAudit:
    checked_rows: int
    findings: tuple[LeakageFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


def _utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


class PurgedWalkForwardSplitter:
    """Create expanding-window folds with a time-based embargo.

    Rows must be supplied in event-time order. A row is eligible for training
    only when its event timestamp is strictly earlier than the test boundary
    minus the embargo. This protects against overlapping labels and delayed
    settlement windows when the caller chooses an appropriate embargo.
    """

    def split(
        self,
        timestamps: Sequence[datetime],
        minimum_train_size: int,
        test_size: int,
        folds: int,
        embargo: timedelta = timedelta(0),
    ) -> tuple[TemporalFold, ...]:
        if minimum_train_size < 1 or test_size < 1 or folds < 1:
            raise ValueError("split dimensions must be positive")
        if embargo < timedelta(0):
            raise ValueError("embargo cannot be negative")
        stamps = [_utc(value, "timestamp") for value in timestamps]
        if any(stamps[index] > stamps[index + 1] for index in range(len(stamps) - 1)):
            raise ValueError("timestamps must be sorted in ascending order")
        required = minimum_train_size + folds * test_size
        if len(stamps) < required:
            raise ValueError("not enough rows for requested folds")
        results: list[TemporalFold] = []
        first_test = len(stamps) - folds * test_size
        for fold_index in range(folds):
            start = first_test + fold_index * test_size
            end = start + test_size
            test_start = stamps[start]
            cutoff = test_start - embargo
            train = tuple(index for index in range(start) if stamps[index] < cutoff)
            test = tuple(range(start, end))
            if len(train) < minimum_train_size:
                raise ValueError("embargo leaves too few training observations")
            results.append(TemporalFold(
                fold=fold_index,
                train_indices=train,
                test_indices=test,
                train_cutoff=cutoff,
                test_start=test_start,
                test_end=stamps[end - 1],
                embargo=embargo,
            ))
        return tuple(results)


def audit_feature_availability(
    event_times: Sequence[datetime],
    feature_available_times: Sequence[datetime],
    label_available_times: Sequence[datetime] | None = None,
) -> TemporalAudit:
    """Detect features or labels unavailable at the prediction event time."""
    if len(event_times) != len(feature_available_times):
        raise ValueError("event and feature availability arrays must align")
    if label_available_times is not None and len(label_available_times) != len(event_times):
        raise ValueError("label availability array must align")
    findings: list[LeakageFinding] = []
    for index, (event, available) in enumerate(zip(event_times, feature_available_times)):
        event_utc = _utc(event, "event time")
        available_utc = _utc(available, "feature availability time")
        if available_utc > event_utc:
            findings.append(LeakageFinding(index, "FUTURE_FEATURE", "feature was unavailable at prediction time"))
        if label_available_times is not None:
            label_time = _utc(label_available_times[index], "label availability time")
            if label_time > event_utc:
                findings.append(LeakageFinding(index, "FUTURE_LABEL", "label was unavailable at prediction time"))
    return TemporalAudit(len(event_times), tuple(findings))


def assert_no_temporal_leakage(audit: TemporalAudit) -> None:
    if not audit.passed:
        codes = sorted({finding.code for finding in audit.findings})
        raise ValueError("temporal leakage detected: " + ", ".join(codes))


def validate_fold_integrity(fold: TemporalFold, row_count: int) -> None:
    """Validate bounds, ordering, and disjointness before model fitting."""
    if row_count < 1:
        raise ValueError("row_count must be positive")
    all_indices = fold.train_indices + fold.test_indices
    if any(index < 0 or index >= row_count for index in all_indices):
        raise IndexError("fold index outside dataset bounds")
    if tuple(sorted(fold.train_indices)) != fold.train_indices:
        raise ValueError("training indices must be ordered")
    if tuple(sorted(fold.test_indices)) != fold.test_indices:
        raise ValueError("test indices must be ordered")
    if max(fold.train_indices) >= min(fold.test_indices):
        raise ValueError("training observations must precede test observations")


def label_maturity_cutoff(
    event_time: datetime,
    label_horizon: timedelta,
    observation_delay: timedelta = timedelta(0),
) -> datetime:
    """Return earliest timestamp at which a horizon label is considered mature."""
    if label_horizon < timedelta(0) or observation_delay < timedelta(0):
        raise ValueError("label horizon and observation delay cannot be negative")
    return _utc(event_time, "event time") + label_horizon + observation_delay


def matured_training_indices(
    event_times: Sequence[datetime],
    label_available_times: Sequence[datetime],
    as_of: datetime,
) -> tuple[int, ...]:
    """Select only rows whose labels were observable by the training cutoff."""
    if len(event_times) != len(label_available_times):
        raise ValueError("event and label arrays must align")
    cutoff = _utc(as_of, "as_of")
    eligible: list[int] = []
    for index, (event, label) in enumerate(zip(event_times, label_available_times)):
        event_utc = _utc(event, "event time")
        label_utc = _utc(label, "label availability time")
        if label_utc < event_utc:
            raise ValueError("label cannot be available before its event")
        if label_utc <= cutoff:
            eligible.append(index)
    return tuple(eligible)
