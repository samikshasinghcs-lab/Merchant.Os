"""Currency-aware arithmetic. Cross-currency arithmetic is deliberately forbidden."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from typing import Iterable, Mapping

_MINOR_UNITS = {"BHD": 3, "JOD": 3, "KWD": 3, "OMR": 3, "TND": 3, "JPY": 0, "KRW": 0}

def decimal_value(value: object) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid decimal value") from exc
    if not result.is_finite():
        raise ValueError("financial values must be finite")
    return result

@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str
    def __post_init__(self) -> None:
        amount = decimal_value(self.amount)
        currency = str(self.currency).upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)
    @property
    def minor_units(self) -> int:
        places = _MINOR_UNITS.get(self.currency, 2)
        quantum = Decimal(1).scaleb(-places)
        return int((self.amount.quantize(quantum, rounding=ROUND_HALF_EVEN) * (10 ** places)))
    def _same(self, other: "Money") -> None:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise ValueError("money operations require matching currencies")
    def __add__(self, other: "Money") -> "Money":
        self._same(other); return Money(self.amount + other.amount, self.currency)
    def __sub__(self, other: "Money") -> "Money":
        self._same(other); return Money(self.amount - other.amount, self.currency)
    def multiply(self, factor: object) -> "Money":
        multiplier = decimal_value(factor)
        return Money(self.amount * multiplier, self.currency)
    def allocate(self, weights: Iterable[object]) -> tuple["Money", ...]:
        values = [decimal_value(item) for item in weights]
        if not values or any(item < 0 for item in values):
            raise ValueError("allocation weights must be non-empty and non-negative")
        total = sum(values, Decimal(0))
        if total == 0:
            raise ValueError("allocation weights cannot all be zero")
        places = _MINOR_UNITS.get(self.currency, 2)
        quantum = Decimal(1).scaleb(-places)
        remaining = self.amount
        parts = []
        for weight in values[:-1]:
            part = (self.amount * weight / total).quantize(quantum, rounding=ROUND_HALF_EVEN)
            parts.append(Money(part, self.currency)); remaining -= part
        parts.append(Money(remaining, self.currency))
        return tuple(parts)

class MoneyBag:
    """A deterministic currency-to-amount accumulator; no implicit FX."""
    def __init__(self, values: Iterable[Money] = ()) -> None:
        self._totals: dict[str, Decimal] = {}
        for value in values: self.add(value)
    def add(self, value: Money) -> None:
        self._totals[value.currency] = self._totals.get(value.currency, Decimal(0)) + value.amount
    def get(self, currency: str) -> Money:
        code = currency.upper()
        return Money(self._totals.get(code, Decimal(0)), code)
    def snapshot(self) -> Mapping[str, str]:
        return {key: str(self._totals[key]) for key in sorted(self._totals)}
    def currencies(self) -> tuple[str, ...]:
        return tuple(sorted(self._totals))
