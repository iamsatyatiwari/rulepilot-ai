"""Inspectable threshold discovery, isolated from rule execution."""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.baseline import BASELINE_RULE
from app.data import stratified_train_validation_test_split
from app.evaluation import EvaluationMetrics, calculate_metrics
from app.rules.engine import evaluate_rule
from app.rules.models import (
    ComparisonOperator,
    Condition,
    LogicalOperator,
    Rule,
    RuleStatus,
    Transaction,
    ruleable_fields,
)

MIN_TRAINING_SUPPORT = 2
MAX_THRESHOLDS_PER_FEATURE = 8


class DiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reason: str | None = None
    seed: int
    training_count: int
    validation_count: int
    test_count: int
    candidates_evaluated: int
    candidate_rule: Rule | None = None
    validation_metrics: EvaluationMetrics | None = None
    baseline_test_metrics: EvaluationMetrics | None = None
    candidate_test_metrics: EvaluationMetrics | None = None
    fraud_missed_by_baseline: list[str]


def _thresholds_from_training(values: Sequence[int | float]) -> list[float]:
    unique = sorted(set(values))
    if len(unique) < 2:
        return []
    boundaries = list(range(1, len(unique)))
    if len(boundaries) > MAX_THRESHOLDS_PER_FEATURE:
        selected_indexes = {
            round(position * (len(boundaries) - 1) / (MAX_THRESHOLDS_PER_FEATURE - 1))
            for position in range(MAX_THRESHOLDS_PER_FEATURE)
        }
        boundaries = [boundaries[index] for index in sorted(selected_indexes)]
    return [
        float((unique[index - 1] + unique[index]) / 2)
        for index in boundaries
    ]


def _make_candidate(field: str, operator: ComparisonOperator, threshold: float, seed: int) -> Rule:
    value_tag = format(threshold, ".8g").replace("-", "m").replace(".", "p")
    operator_tag = operator.value.replace("_", "-")
    rule_id = f"DISC-{seed}-{field}-{operator_tag}-{value_tag}"
    rule_id = re.sub(r"[^A-Za-z0-9._-]", "-", rule_id)[:64]
    return Rule(
        rule_id=rule_id,
        name=f"Candidate: {field} {operator.value} {threshold:g}",
        description="A single numeric threshold proposed from the training split.",
        rationale=(
            "The condition was generated from a training-only feature threshold "
            "and retained based on validation-split evidence."
        ),
        conditions=[Condition(field=field, operator=operator, value=threshold)],
        logical_operator=LogicalOperator.AND,
        status=RuleStatus.DRAFT,
        created_by="threshold-discovery",
    )


def _predictions(rule: Rule, records: Sequence[Transaction]) -> list[bool]:
    return [evaluate_rule(rule, record) for record in records]


def discover_candidate(
    training: Sequence[Transaction], validation: Sequence[Transaction], seed: int = 41
) -> tuple[Rule | None, EvaluationMetrics | None, int, str | None]:
    """Search only training-derived thresholds; select using validation labels.

    This function deliberately has no test-data parameter. It does not access
    or retain labels from any test split.
    """
    if len(training) < 8 or len(validation) < 4:
        return None, None, 0, "insufficient records for training and validation splits"
    if any(row.ground_truth_fraud is None for row in (*training, *validation)):
        return None, None, 0, "ground-truth labels are required for discovery"
    if len({row.ground_truth_fraud for row in training}) < 2:
        return None, None, 0, "training split must contain both legitimate and fraud labels"
    if len({row.ground_truth_fraud for row in validation}) < 2:
        return None, None, 0, "validation split must contain both legitimate and fraud labels"

    candidates: list[tuple[Rule, EvaluationMetrics, float]] = []
    candidate_count = 0
    for field in sorted(ruleable_fields()):
        training_values = [getattr(row, field) for row in training]
        if any(value is None for value in training_values):
            continue
        thresholds = _thresholds_from_training(training_values)
        for threshold in thresholds:
            for operator in (
                ComparisonOperator.GREATER_THAN,
                ComparisonOperator.LESS_THAN_OR_EQUAL,
            ):
                rule = _make_candidate(field, operator, threshold, seed)
                train_flags = _predictions(rule, training)
                support = sum(train_flags)
                if support < MIN_TRAINING_SUPPORT or support > len(training) - MIN_TRAINING_SUPPORT:
                    continue
                validation_flags = _predictions(rule, validation)
                validation_support = sum(validation_flags)
                if validation_support == 0 or validation_support == len(validation):
                    continue
                labels = [bool(row.ground_truth_fraud) for row in validation]
                metrics = calculate_metrics(validation_flags, labels)
                candidate_count += 1
                candidates.append((rule, metrics, _f1(metrics)))

    if not candidates:
        return None, None, candidate_count, "no non-degenerate threshold met minimum support"

    # Python's stable max preserves sorted feature/operator/threshold order on ties.
    best_rule, best_metrics, _ = max(
        candidates,
        key=lambda item: (
            item[2],
            item[1].precision,
            item[1].recall,
            -item[1].false_positive_rate,
        ),
    )
    return best_rule, best_metrics, candidate_count, None


def _f1(metrics: EvaluationMetrics) -> float:
    denominator = metrics.precision + metrics.recall
    return 2 * metrics.precision * metrics.recall / denominator if denominator else 0.0


def run_discovery(
    transactions: list[Transaction], seed: int = 41
) -> DiscoveryReport:
    """Discover on train/validation, then evaluate the chosen candidate once on test."""
    training, validation, test = stratified_train_validation_test_split(transactions, seed)
    candidate, validation_metrics, candidates_evaluated, reason = discover_candidate(
        training, validation, seed
    )

    baseline_predictions = _predictions(BASELINE_RULE, test)
    test_labels = [bool(row.ground_truth_fraud) for row in test]
    baseline_metrics = calculate_metrics(baseline_predictions, test_labels)
    missed = [
        row.transaction_id or ""
        for row, flagged, label in zip(test, baseline_predictions, test_labels)
        if label and not flagged
    ]

    candidate_test_metrics = None
    if candidate is not None:
        # The selected candidate is evaluated exactly once on the held-out test records.
        candidate_predictions = _predictions(candidate, test)
        candidate_test_metrics = calculate_metrics(candidate_predictions, test_labels)

    return DiscoveryReport(
        status="candidate_found" if candidate is not None else "insufficient_evidence",
        reason=reason,
        seed=seed,
        training_count=len(training),
        validation_count=len(validation),
        test_count=len(test),
        candidates_evaluated=candidates_evaluated,
        candidate_rule=candidate,
        validation_metrics=validation_metrics,
        baseline_test_metrics=baseline_metrics,
        candidate_test_metrics=candidate_test_metrics,
        fraud_missed_by_baseline=missed,
    )
