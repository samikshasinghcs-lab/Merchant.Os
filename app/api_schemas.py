"""Strict, bounded request schemas for tenant-scoped public API inputs.

Client-supplied fields are treated as untrusted data. Unknown fields are rejected,
financial values are bounded, and server-owned fields (tenant/status/classification)
are intentionally absent from request models.
"""
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ShortId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Product = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TenantOrderCreate(StrictRequest):
    amount: Annotated[Decimal, Field(gt=Decimal("0"), max_digits=14, decimal_places=2)]
    currency: Currency = "USD"
    customer_id: ShortId | None = None
    customer_name: Name | None = None
    product: Product = ""

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper() if isinstance(value, str) else value

    @field_validator("amount")
    @classmethod
    def finite_money(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount must be finite")
        return value


class TenantReviewCreate(StrictRequest):
    text: Annotated[str, StringConstraints(min_length=1, max_length=10_000)]
    rating: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None
    customer_id: ShortId | None = None
    customer_name: Name | None = None
    order_id: ShortId | None = None
    product: Product | None = None

    @field_validator("text")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Review text is required")
        return value.strip()
