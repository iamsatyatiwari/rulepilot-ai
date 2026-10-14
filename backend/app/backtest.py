"""Shared, deterministic baseline-versus-candidate comparison on one split."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.baseline import BASELINE_RULE
from app.data import stratified_train_validation_test_split
from app.evaluation import EvaluationMetrics, calculate_metrics
from app.rules.engine import evaluate_rule
from app.rules.models import Rule, Transaction

SplitName = Literal["train", "validation", "test"]


class SplitComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluated_split: SplitName
    seed: int
    baseline_metrics: EvaluationMetrics
    candidate_metrics: EvaluationMetrics
    combined_metrics: EvaluationMetrics
    fraud_missed_by_baseline: list[str]
    fraud_missed_by_candidate: list[str]
    fraud_missed_by_combined: list[str]


def _missed(records: Sequence[Transaction], flags: Sequence[bool], labels: Sequence[bool]) -> list[str]:
    return [
        record.transaction_id or ""
        for record, flagged, label in zip(records, flags, labels)
        if label and not flagged
    ]


def compare_records(
    candidate: Rule,
    records: Sequence[Transaction],
    split: SplitName,
    seed: int,
    reference_rules: Sequence[Rule] = (BASELINE_RULE,),
) -> SplitComparison:
    """Compare the reference rule set, the candidate, and reference OR candidate.

    ``baseline_metrics`` describe the reference rule set: the documented baseline
    plus any human-approved rules, combined with OR.
    """
    labels = [bool(record.ground_truth_fraud) for record in records]
    baseline_flags = [
        any(evaluate_rule(rule, record) for rule in reference_rules) for record in records
    ]
    candidate_flags = [evaluate_rule(candidate, record) for record in records]
    combined_flags = [b or c for b, c in zip(baseline_flags, candidate_flags)]
    return SplitComparison(
        evaluated_split=split,
        seed=seed,
        baseline_metrics=calculate_metrics(baseline_flags, labels),
        candidate_metrics=calculate_metrics(candidate_flags, labels),
        combined_metrics=calculate_metrics(combined_flags, labels),
        fraud_missed_by_baseline=_missed(records, baseline_flags, labels),
        fraud_missed_by_candidate=_missed(records, candidate_flags, labels),
        fraud_missed_by_combined=_missed(records, combined_flags, labels),
    )


def compare_on_split(
    candidate: Rule, transactions: list[Transaction], seed: int, split: SplitName
) -> SplitComparison:
    """Split a dataset deterministically and compare rules on the requested split."""
    train, validation, test = stratified_train_validation_test_split(transactions, seed)
    records = {"train": train, "validation": validation, "test": test}[split]
    return compare_records(candidate, records, split, seed)
