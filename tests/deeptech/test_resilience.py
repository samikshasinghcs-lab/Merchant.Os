from datetime import datetime, timedelta, timezone

import pytest

from app.deeptech.research.resilience import (
    BreakerState,
    CircuitBreaker,
    CircuitOpenError,
    DeadLetterQueue,
    DeadLetterRecord,
    ExponentialBackoff,
)


class FakeClock:
    def __init__(self):
        self.value = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, delta):
        self.value += delta


def test_breaker_opens_after_failure_threshold():
    clock = FakeClock()
    breaker = CircuitBreaker("paypal-read", 2, timedelta(seconds=10), clock)
    breaker.record_failure()
    assert breaker.snapshot().state is BreakerState.CLOSED
    breaker.record_failure()
    assert breaker.snapshot().state is BreakerState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.acquire()


def test_breaker_allows_only_one_half_open_probe():
    clock = FakeClock()
    breaker = CircuitBreaker("provider", 1, timedelta(seconds=5), clock)
    breaker.record_failure()
    clock.advance(timedelta(seconds=5))
    breaker.acquire()
    with pytest.raises(CircuitOpenError):
        breaker.acquire()
    breaker.record_success()
    assert breaker.snapshot().state is BreakerState.CLOSED


def test_failed_half_open_probe_reopens_breaker():
    clock = FakeClock()
    breaker = CircuitBreaker("provider", 1, timedelta(seconds=5), clock)
    breaker.record_failure()
    clock.advance(timedelta(seconds=5))
    breaker.acquire()
    breaker.record_failure()
    assert breaker.snapshot().state is BreakerState.OPEN


def test_call_records_success_and_failure():
    breaker = CircuitBreaker("worker", 1)
    assert breaker.call(lambda value: value + 1, 2) == 3
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("failure")))
    assert breaker.snapshot().state is BreakerState.OPEN


def test_backoff_is_bounded_and_deterministic():
    policy = ExponentialBackoff(1, 5, 3, jitter_fraction=0.2)
    assert policy.decide(1, 0.5).delay_seconds == 1
    assert abs(policy.decide(3, 1).delay_seconds - 4.8) < 1e-12
    assert not policy.decide(4).allowed


def test_dead_letter_queue_is_tenant_scoped_and_bounded():
    queue = DeadLetterQueue(capacity=2)
    now = datetime.now(timezone.utc)
    queue.put(DeadLetterRecord("e1", "t1", "invalid", 1, now, now))
    queue.put(DeadLetterRecord("e1", "t2", "invalid", 1, now, now))
    assert queue.get("t1", "e1") is not None
    assert queue.get("other", "e1") is None
    queue.put(DeadLetterRecord("e2", "t1", "timeout", 2, now, now))
    queue.put(DeadLetterRecord("e3", "t1", "schema", 1, now, now))
    assert len(queue) == 2
    assert queue.get("t1", "e1") is None


def test_dead_letter_duplicate_updates_attempts_without_duplicate_entry():
    queue = DeadLetterQueue()
    now = datetime.now(timezone.utc)
    queue.put(DeadLetterRecord("e1", "t1", "timeout", 1, now, now))
    queue.put(DeadLetterRecord("e1", "t1", "timeout", 3, now, now + timedelta(seconds=5)))
    assert len(queue) == 1
    assert queue.get("t1", "e1").attempts == 3


def test_dead_letter_remove_is_idempotent():
    queue = DeadLetterQueue()
    now = datetime.now(timezone.utc)
    queue.put(DeadLetterRecord("e1", "t1", "invalid", 1, now, now))
    assert queue.remove("t1", "e1")
    assert not queue.remove("t1", "e1")
