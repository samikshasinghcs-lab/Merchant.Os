"""Typed, validation-focused domain objects for the MerchantOS intelligence layer."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping
import re

_CURRENCY = re.compile(r"^[A-Z]{3}$")

class TransactionStatus(str, Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    DISPUTED = "DISPUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True, slots=True)
class Transaction:
    transaction_id: str
    merchant_id: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    status: TransactionStatus = TransactionStatus.COMPLETED
    customer_id: str | None = None
    product_id: str | None = None
    category: str | None = None
    channel: str | None = None
    country: str | None = None
    payment_method: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not self.transaction_id or not self.merchant_id:
            raise ValueError("transaction_id and merchant_id are required")
        try:
            amount = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("amount must be a valid decimal") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("amount must be finite and non-negative")
        object.__setattr__(self, "amount", amount)
        currency = str(self.currency).upper()
        if not _CURRENCY.fullmatch(currency):
            raise ValueError("currency must be a three-letter uppercase code")
        object.__setattr__(self, "currency", currency)
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(timezone.utc))
        if not isinstance(self.status, TransactionStatus):
            object.__setattr__(self, "status", TransactionStatus(str(self.status).upper()))
        # Metadata is observational input. Keep a shallow defensive copy.
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Transaction":
        timestamp = raw.get("occurred_at") or raw.get("created_at")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if not isinstance(timestamp, datetime):
            raise ValueError("occurred_at must be an ISO timestamp or datetime")
        return cls(
            transaction_id=str(raw["transaction_id"]), merchant_id=str(raw["merchant_id"]),
            amount=Decimal(str(raw["amount"])), currency=str(raw["currency"]),
            occurred_at=timestamp, status=TransactionStatus(str(raw.get("status", "COMPLETED")).upper()),
            customer_id=_optional(raw.get("customer_id")), product_id=_optional(raw.get("product_id")),
            category=_optional(raw.get("category")), channel=_optional(raw.get("channel")),
            country=_optional(raw.get("country")), payment_method=_optional(raw.get("payment_method")),
            metadata=raw.get("metadata") or {},
        )

@dataclass(frozen=True, slots=True)
class AnomalyFinding:
    transaction_id: str
    score: float
    severity: str
    signals: tuple[str, ...]
    baseline: Mapping[str, float]
    observed: Mapping[str, float]

@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    order_count: int
    average_order_value: Decimal
    refund_rate: float = 0.04
    dispute_rate: float = 0.01
    variable_cost_rate: float = 0.35
    payment_fee_rate: float = 0.029
    fixed_cost: Decimal = Decimal("0")
    refund_loss_multiplier: float = 1.0
    dispute_loss_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.order_count < 0:
            raise ValueError("order_count must be non-negative")
        aov = Decimal(str(self.average_order_value))
        if not aov.is_finite() or aov < 0:
            raise ValueError("average_order_value must be finite and non-negative")
        object.__setattr__(self, "average_order_value", aov)
        object.__setattr__(self, "fixed_cost", Decimal(str(self.fixed_cost)))
        for key in ("refund_rate", "dispute_rate", "variable_cost_rate", "payment_fee_rate"):
            value = float(getattr(self, key))
            if not 0 <= value <= 1:
                raise ValueError(f"{key} must be between 0 and 1")
        if self.refund_loss_multiplier < 0 or self.dispute_loss_multiplier < 0:
            raise ValueError("loss multipliers must be non-negative")

@dataclass(frozen=True, slots=True)
class SimulationResult:
    scenario_name: str
    iterations: int
    mean_net_revenue: float
    median_net_revenue: float
    p05_net_revenue: float
    p95_net_revenue: float
    probability_of_loss: float
    assumptions: Mapping[str, Any]
    seed: int

def _optional(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
