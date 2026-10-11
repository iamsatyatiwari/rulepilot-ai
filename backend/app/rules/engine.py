"""Deterministic rule execution with no dynamic code evaluation."""

from collections.abc import Mapping

from pydantic import ValidationError

from app.rules.models import (
    ComparisonOperator,
    LogicalOperator,
    Rule,
    Transaction,
)


def _compare(left: int | float, operator: ComparisonOperator, right: int | float) -> bool:
    if operator is ComparisonOperator.GREATER_THAN:
        return left > right
    if operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
        return left >= right
    if operator is ComparisonOperator.LESS_THAN:
        return left < right
    if operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
        return left <= right
    if operator is ComparisonOperator.EQUALS:
        return left == right
    if operator is ComparisonOperator.NOT_EQUALS:
        return left != right
    raise ValueError(f"unsupported operator: {operator}")


def evaluate_rule(rule: Rule | Mapping[str, object], transaction: Transaction | Mapping[str, object]) -> bool:
    """Return whether a transaction is flagged by a validated rule.

    A malformed rule raises Pydantic's clear ``ValidationError``. Invalid or
    incomplete transaction data returns ``False`` (fail closed) rather than
    guessing. All referenced fields must be present and valid before AND/OR
    logic is applied, so an OR cannot hide a missing feature.
    """
    validated_rule = rule if isinstance(rule, Rule) else Rule.model_validate(rule)
    try:
        validated_transaction = (
            transaction
            if isinstance(transaction, Transaction)
            else Transaction.model_validate(transaction)
        )
    except ValidationError:
        return False

    values: list[bool] = []
    for condition in validated_rule.conditions:
        feature_value = getattr(validated_transaction, condition.field)
        if feature_value is None or isinstance(feature_value, bool):
            return False
        values.append(_compare(feature_value, condition.operator, condition.value))

    if validated_rule.logical_operator is LogicalOperator.AND:
        return all(values)
    return any(values)
