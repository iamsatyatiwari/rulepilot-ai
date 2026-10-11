"""Documented, fixed baseline rule used for transparent comparisons."""

from app.rules.models import (
    ComparisonOperator,
    Condition,
    LogicalOperator,
    Rule,
    RuleStatus,
)

BASELINE_RULE = Rule(
    rule_id="RP-BASELINE-001",
    name="High transaction amount baseline",
    description="Flags a transaction when its amount is at least 1,500 synthetic currency units.",
    rationale=(
        "A simple, documented starting point for comparing candidate rules. "
        "The threshold is illustrative and is not calibrated for real financial data."
    ),
    conditions=[
        Condition(
            field="amount",
            operator=ComparisonOperator.GREATER_THAN_OR_EQUAL,
            value=1500,
        )
    ],
    logical_operator=LogicalOperator.AND,
    status=RuleStatus.APPROVED,
    version=1,
    created_by="rulepilot-baseline",
)
