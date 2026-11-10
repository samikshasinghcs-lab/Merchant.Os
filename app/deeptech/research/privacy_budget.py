"""Experimental Gaussian-noise and basic-composition privacy helpers.

This module is not a complete DP system: callers must bound contributions,
clip data to a declared sensitivity, protect randomness, and persist/account
for releases transactionally. The calibration uses the classical Gaussian
bound for 0 < epsilon <= 1 and 0 < delta < 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log, sqrt
from threading import RLock

@dataclass(frozen=True, slots=True)
class PrivacyRelease:
    mechanism: str
    epsilon: float
    delta: float
    sensitivity: float
    noise_sigma: float

class GaussianMechanism:
    def calibrate(self, sensitivity: float, epsilon: float, delta: float) -> PrivacyRelease:
        values = (sensitivity, epsilon, delta)
        if not all(isfinite(float(value)) for value in values):
            raise ValueError("privacy parameters must be finite")
        if sensitivity < 0 or not 0 < epsilon <= 1 or not 0 < delta < 1:
            raise ValueError("require sensitivity >= 0, 0 < epsilon <= 1, and 0 < delta < 1")
        sigma = sensitivity * sqrt(2 * log(1.25 / delta)) / epsilon
        return PrivacyRelease("gaussian", float(epsilon), float(delta), float(sensitivity), float(sigma))

    def add_noise(self, value: float, release: PrivacyRelease, rng) -> float:
        if release.mechanism != "gaussian":
            raise ValueError("unsupported mechanism")
        if not all(isfinite(float(x)) for x in (value, release.epsilon, release.delta, release.sensitivity, release.noise_sigma)):
            raise ValueError("release and value must be finite")
        if release.epsilon <= 0 or not 0 < release.delta < 1 or release.sensitivity < 0 or release.noise_sigma < 0:
            raise ValueError("invalid release parameters")
        return float(value) + rng.gauss(0, release.noise_sigma)

class BasicPrivacyAccountant:
    """In-memory basic composition; not durable or safe across processes."""
    def __init__(self, max_epsilon: float, max_delta: float):
        if not isfinite(float(max_epsilon)) or not isfinite(float(max_delta)) or max_epsilon <= 0 or not 0 < max_delta < 1:
            raise ValueError("invalid privacy budget")
        self.max_epsilon = float(max_epsilon)
        self.max_delta = float(max_delta)
        self._releases: list[PrivacyRelease] = []
        self._lock = RLock()

    @staticmethod
    def _validate_spend(epsilon: float, delta: float) -> None:
        if not isfinite(float(epsilon)) or not isfinite(float(delta)) or epsilon <= 0 or not 0 <= delta < 1:
            raise ValueError("spend must have finite epsilon > 0 and delta in [0, 1)")

    def can_spend(self, epsilon: float, delta: float) -> bool:
        self._validate_spend(epsilon, delta)
        with self._lock:
            return (sum(r.epsilon for r in self._releases) + epsilon <= self.max_epsilon
                    and sum(r.delta for r in self._releases) + delta <= self.max_delta)

    def record(self, release: PrivacyRelease) -> None:
        if release.mechanism != "gaussian":
            raise ValueError("unsupported privacy mechanism")
        self._validate_spend(release.epsilon, release.delta)
        if not all(isfinite(float(x)) for x in (release.sensitivity, release.noise_sigma)) or release.sensitivity < 0 or release.noise_sigma < 0:
            raise ValueError("invalid release calibration")
        with self._lock:
            if (sum(r.epsilon for r in self._releases) + release.epsilon > self.max_epsilon
                    or sum(r.delta for r in self._releases) + release.delta > self.max_delta):
                raise RuntimeError("privacy budget exhausted")
            self._releases.append(release)

    def spent(self) -> tuple[float, float]:
        with self._lock:
            return sum(r.epsilon for r in self._releases), sum(r.delta for r in self._releases)

    def remaining(self) -> tuple[float, float]:
        epsilon, delta = self.spent()
        return self.max_epsilon - epsilon, self.max_delta - delta
