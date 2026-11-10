"""Bounded reliability primitives for analytical and provider-adapter workers.

The circuit breaker is process-local. It is useful for protecting a worker
from repeatedly calling a failing dependency, but it is not a distributed
coordination mechanism. Persisted or cross-process breakers need shared state.
No function in this module performs network I/O or retries financial writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from threading import RLock
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class BreakerSnapshot:
    name: str
    state: BreakerState
    consecutive_failures: int
    opened_at: datetime | None
    retry_after: datetime | None
    probe_in_flight: bool


class CircuitOpenError(RuntimeError):
    """Raised when a protected dependency is not currently callable."""


class CircuitBreaker:
    """Thread-safe circuit breaker with one half-open probe at a time."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: timedelta = timedelta(seconds=30),
        clock: Callable[[], datetime] | None = None,
    ):
        if not name or failure_threshold < 1 or reset_timeout.total_seconds() <= 0:
            raise ValueError("invalid circuit breaker configuration")
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at: datetime | None = None
        self._probe_in_flight = False
        self._lock = RLock()

    def _now(self) -> datetime:
        stamp = self._clock()
        if stamp.tzinfo is None:
            raise ValueError("breaker clock must return timezone-aware timestamps")
        return stamp.astimezone(timezone.utc)

    def acquire(self) -> None:
        """Authorize one call attempt or raise CircuitOpenError."""
        with self._lock:
            now = self._now()
            if self._state is BreakerState.CLOSED:
                return
            if self._state is BreakerState.OPEN:
                assert self._opened_at is not None
                if now < self._opened_at + self.reset_timeout:
                    raise CircuitOpenError(f"{self.name} circuit is open")
                self._state = BreakerState.HALF_OPEN
            if self._state is BreakerState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitOpenError(f"{self.name} recovery probe already in flight")
                self._probe_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = BreakerState.CLOSED
            self._opened_at = None
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._probe_in_flight = False
            if self._state is BreakerState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = self._now()

    def call(self, operation: Callable[..., T], *args, **kwargs) -> T:
        self.acquire()
        try:
            result = operation(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def snapshot(self) -> BreakerSnapshot:
        with self._lock:
            retry_after = None
            if self._opened_at is not None:
                retry_after = self._opened_at + self.reset_timeout
            return BreakerSnapshot(
                self.name, self._state, self._failures,
                self._opened_at, retry_after, self._probe_in_flight,
            )

    def force_open(self) -> None:
        """Administrative fail-closed operation, intended for tests/ops."""
        with self._lock:
            self._state = BreakerState.OPEN
            self._opened_at = self._now()
            self._probe_in_flight = False

    def reset(self) -> None:
        with self._lock:
            self._state = BreakerState.CLOSED
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False


@dataclass(frozen=True, slots=True)
class RetryDecision:
    attempt: int
    delay_seconds: float
    allowed: bool
    reason: str


class ExponentialBackoff:
    """Calculate bounded retry delays; does not execute retries."""

    def __init__(
        self,
        base_seconds: float = 0.25,
        maximum_seconds: float = 30.0,
        maximum_attempts: int = 5,
        jitter_fraction: float = 0.0,
    ):
        values = (base_seconds, maximum_seconds, jitter_fraction)
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("backoff parameters must be finite")
        if base_seconds <= 0 or maximum_seconds < base_seconds:
            raise ValueError("invalid backoff bounds")
        if maximum_attempts < 1 or not 0 <= jitter_fraction <= 1:
            raise ValueError("invalid retry configuration")
        self.base_seconds = float(base_seconds)
        self.maximum_seconds = float(maximum_seconds)
        self.maximum_attempts = maximum_attempts
        self.jitter_fraction = float(jitter_fraction)

    def decide(self, attempt: int, deterministic_jitter: float = 0.0) -> RetryDecision:
        if attempt < 1:
            raise ValueError("attempt numbering starts at one")
        if not 0 <= deterministic_jitter <= 1:
            raise ValueError("deterministic_jitter must be in [0, 1]")
        if attempt > self.maximum_attempts:
            return RetryDecision(attempt, 0.0, False, "attempt_limit_reached")
        raw = min(self.maximum_seconds, self.base_seconds * (2 ** (attempt - 1)))
        # Jitter is deterministic when supplied by the caller, enabling
        # reproducible tests and avoiding hidden random state in policy code.
        multiplier = 1 - self.jitter_fraction + 2 * self.jitter_fraction * deterministic_jitter
        delay = min(self.maximum_seconds, raw * multiplier)
        return RetryDecision(attempt, delay, True, "retry_budget_available")


@dataclass(frozen=True, slots=True)
class DeadLetterRecord:
    event_id: str
    tenant_id: str
    reason_code: str
    attempts: int
    first_seen: datetime
    last_seen: datetime

    def __post_init__(self) -> None:
        if not self.event_id or not self.tenant_id or not self.reason_code:
            raise ValueError("dead-letter identity and reason are required")
        if self.attempts < 1:
            raise ValueError("attempts must be positive")
        first = self.first_seen
        last = self.last_seen
        if first.tzinfo is None or last.tzinfo is None:
            raise ValueError("dead-letter timestamps must be timezone-aware")
        if last < first:
            raise ValueError("last_seen cannot precede first_seen")


class DeadLetterQueue:
    """Bounded in-memory quarantine with tenant-scoped lookup."""

    def __init__(self, capacity: int = 10_000):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._records: dict[tuple[str, str], DeadLetterRecord] = {}
        self._order: list[tuple[str, str]] = []
        self._lock = RLock()

    def put(self, record: DeadLetterRecord) -> None:
        key = (record.tenant_id, record.event_id)
        with self._lock:
            if key in self._records:
                previous = self._records[key]
                record = DeadLetterRecord(
                    event_id=record.event_id,
                    tenant_id=record.tenant_id,
                    reason_code=record.reason_code,
                    attempts=max(previous.attempts, record.attempts),
                    first_seen=min(previous.first_seen, record.first_seen),
                    last_seen=max(previous.last_seen, record.last_seen),
                )
                self._records[key] = record
                return
            while len(self._order) >= self.capacity:
                expired = self._order.pop(0)
                self._records.pop(expired, None)
            self._records[key] = record
            self._order.append(key)

    def get(self, tenant_id: str, event_id: str) -> DeadLetterRecord | None:
        with self._lock:
            return self._records.get((tenant_id, event_id))

    def list_for_tenant(self, tenant_id: str) -> tuple[DeadLetterRecord, ...]:
        with self._lock:
            return tuple(
                self._records[key] for key in self._order
                if key[0] == tenant_id and key in self._records
            )

    def remove(self, tenant_id: str, event_id: str) -> bool:
        key = (tenant_id, event_id)
        with self._lock:
            if key not in self._records:
                return False
            del self._records[key]
            self._order.remove(key)
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
