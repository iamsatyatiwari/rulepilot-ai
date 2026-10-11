from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.baseline import BASELINE_RULE
from app.rules.engine import evaluate_rule
from app.rules.models import Rule


def make_rule(conditions, logical_operator="and"):
    return Rule.model_validate(
        {
            "rule_id": "TEST-RULE-01",
            "name": "Test rule",
            "description": "A rule used by unit tests.",
            "rationale": "It validates deterministic behavior.",
            "conditions": conditions,
            "logical_operator": logical_operator,
            "status": "draft",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )


@pytest.mark.parametrize(
    ("operator", "feature", "threshold", "expected"),
    [
        ("greater_than", 10, 10, False),
        ("greater_than", 11, 10, True),
        ("greater_than_or_equal", 10, 10, True),
        ("less_than", 9, 10, True),
        ("less_than", 10, 10, False),
        ("less_than_or_equal", 10, 10, True),
        ("equals", 10, 10, True),
        ("not_equals", 9, 10, True),
    ],
)
def test_supported_condition_operators(operator, feature, threshold, expected):
    rule = make_rule([{"field": "amount", "operator": operator, "value": threshold}])
    assert evaluate_rule(rule, {"amount": feature}) is expected


def test_and_requires_every_condition():
    rule = make_rule(
        [
            {"field": "amount", "operator": "greater_than", "value": 100},
            {"field": "account_age_days", "operator": "less_than", "value": 30},
        ],
        "and",
    )
    assert evaluate_rule(rule, {"amount": 101, "account_age_days": 20}) is True
    assert evaluate_rule(rule, {"amount": 101, "account_age_days": 90}) is False


def test_or_requires_one_true_condition():
    rule = make_rule(
        [
            {"field": "amount", "operator": "greater_than", "value": 100},
            {"field": "account_age_days", "operator": "less_than", "value": 30},
        ],
        "or",
    )
    assert evaluate_rule(rule, {"amount": 101, "account_age_days": 90}) is True
    assert evaluate_rule(rule, {"amount": 10, "account_age_days": 90}) is False


@pytest.mark.parametrize(
    "condition",
    [
        {"field": "ground_truth_fraud", "operator": "equals", "value": 1},
        {"field": "arbitrary_python", "operator": "equals", "value": 1},
        {"field": "amount", "operator": "exec", "value": 1},
        {"field": "amount", "operator": "equals", "value": "1"},
        {"field": "amount", "operator": "equals", "value": True},
        {"field": "amount", "operator": "equals", "value": float("nan")},
    ],
)
def test_invalid_fields_operators_and_values_are_rejected(condition):
    with pytest.raises(ValidationError):
        make_rule([condition])


def test_malformed_rules_are_rejected():
    with pytest.raises(ValidationError):
        make_rule([])
    with pytest.raises(ValidationError):
        make_rule(
            [
                {"field": "amount", "operator": "equals", "value": 1},
                {"field": "amount", "operator": "equals", "value": 1},
            ]
        )
    with pytest.raises(ValidationError):
        Rule.model_validate({"rule_id": "bad", "unexpected": "field"})


def test_missing_and_invalid_transaction_features_fail_closed():
    rule = make_rule(
        [
            {"field": "amount", "operator": "greater_than", "value": 10},
            {"field": "account_age_days", "operator": "less_than", "value": 30},
        ],
        "or",
    )
    assert evaluate_rule(rule, {"amount": 20}) is False
    assert evaluate_rule(rule, {"amount": "20", "account_age_days": 10}) is False
    assert evaluate_rule(rule, {"amount": float("nan"), "account_age_days": 10}) is False
    assert evaluate_rule(rule, {"amount": 20, "account_age_days": 10, "shell": "ignored?"}) is False


def test_baseline_rule_is_explicit_and_deterministic():
    assert BASELINE_RULE.rule_id == "RP-BASELINE-001"
    assert evaluate_rule(BASELINE_RULE, {"amount": 1500}) is True
    assert evaluate_rule(BASELINE_RULE, {"amount": 1499.99}) is False
