"""Validated immutable records shared by research subsystems."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence

class Direction(str, Enum):
    HIGHER = "higher"
    LOWER = "lower"
    TWO_SIDED = "two_sided"

class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    merchant_id: str
    occurred_at: datetime
    amount: Decimal
    currency: str
    attributes: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)
    def __post_init__(self) -> None:
        if not self.observation_id or not self.merchant_id:
            raise ValueError("observation and merchant identifiers are required")
        stamp = self.occurred_at
        if stamp.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", stamp.astimezone(timezone.utc))
        value = Decimal(str(self.amount))
        if not value.is_finite() or value < 0:
            raise ValueError("amount must be finite and non-negative")
        object.__setattr__(self, "amount", value)
        code = str(self.currency).upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("currency must be a three-letter code")
        object.__setattr__(self, "currency", code)
        object.__setattr__(self, "attributes", dict(self.attributes or {}))

@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    score: float
    severity: str
    explanation: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    confidence: Confidence = Confidence.MEDIUM
    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("finding code is required")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be in [0, 1]")
        if self.severity not in {"info", "low", "medium", "high", "critical"}:
            raise ValueError("unsupported severity")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "evidence", dict(self.evidence or {}))

@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    value: float
    unit: str = ""
    direction: Direction = Direction.TWO_SIDED
    sample_size: int = 0
    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("metric name is required")
        if self.sample_size < 0:
            raise ValueError("sample_size cannot be negative")

@dataclass(frozen=True, slots=True)
class ModelResult:
    model_name: str
    model_version: str
    predictions: Sequence[float]
    explanations: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if not self.model_name or not self.model_version:
            raise ValueError("model identity is required")
        if len(self.explanations) not in (0, len(self.predictions)):
            raise ValueError("explanations must be empty or match predictions")
        for value in self.predictions:
            if not 0 <= float(value) <= 1:
                raise ValueError("probability predictions must be in [0, 1]")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

def require_finite(values: Sequence[float], name: str = "values") -> list[float]:
    result = [float(value) for value in values]
    if any(not __import__("math").isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result
