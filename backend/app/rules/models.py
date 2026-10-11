"""Pydantic schemas for transaction records and safe, explicit rules."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

NumericValue = Union[StrictInt, StrictFloat]


class Transaction(BaseModel):
    """Synthetic transaction schema; only marked numeric features are ruleable."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: StrictStr | None = None
    amount: NumericValue | None = Field(
        default=None, json_schema_extra={"rule_eligible": True}
    )
    account_age_days: StrictInt | None = Field(
        default=None, json_schema_extra={"rule_eligible": True}
    )
    transactions_24h: StrictInt | None = Field(
        default=None, json_schema_extra={"rule_eligible": True}
    )
    distance_from_home_km: NumericValue | None = Field(
        default=None, json_schema_extra={"rule_eligible": True}
    )
    ground_truth_fraud: StrictBool | None = None

    @field_validator("amount", "distance_from_home_km")
    @classmethod
    def finite_float_features(cls, value: int | float | None) -> int | float | None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("feature values must be finite numbers")
        return value


def ruleable_fields() -> frozenset[str]:
    """Return the feature allowlist from Transaction field metadata."""
    return frozenset(
        name
        for name, field_info in Transaction.model_fields.items()
        if (field_info.json_schema_extra or {}).get("rule_eligible") is True
    )


class ComparisonOperator(str, Enum):
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"


class RuleStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    operator: ComparisonOperator
    value: NumericValue

    @field_validator("value")
    @classmethod
    def finite_condition_value(cls, value: int | float) -> int | float:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("condition values must be finite numbers")
        return value

    @field_validator("field")
    @classmethod
    def allowlisted_field(cls, value: str) -> str:
        if value not in ruleable_fields():
            allowed = ", ".join(sorted(ruleable_fields()))
            raise ValueError(f"unknown or non-ruleable field {value!r}; allowed: {allowed}")
        return value


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: Annotated[StrictStr, Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    name: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    description: Annotated[StrictStr, Field(min_length=1, max_length=500)]
    rationale: Annotated[StrictStr, Field(min_length=1, max_length=1000)]
    conditions: Annotated[list[Condition], Field(min_length=1, max_length=10)]
    logical_operator: LogicalOperator
    status: RuleStatus = RuleStatus.DRAFT
    version: Annotated[StrictInt, Field(ge=1)] = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Annotated[StrictStr, Field(min_length=1, max_length=100)] = "system"

    @field_validator("created_at")
    @classmethod
    def timezone_aware_creation_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value

    @model_validator(mode="after")
    def reject_duplicate_conditions(self) -> Rule:
        signatures = [
            (condition.field, condition.operator, condition.value)
            for condition in self.conditions
        ]
        if len(signatures) != len(set(signatures)):
            raise ValueError("duplicate conditions are not allowed")
        return self
