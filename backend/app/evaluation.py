"""Confusion-matrix metrics for deterministic predictions."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, StrictBool


class EvaluationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    false_positive_rate: float
    total_flagged: int
    total_evaluated: int


def calculate_metrics(
    predictions: Sequence[bool], labels: Sequence[bool]
) -> EvaluationMetrics:
    """Calculate binary classification metrics.

    Precision, recall, and false-positive rate are defined as 0.0 when their
    denominator is zero. Empty aligned sequences are valid and return zeroes.
    """
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have the same length")
    if any(type(value) is not bool for value in (*predictions, *labels)):
        raise ValueError("predictions and labels must contain only booleans")

    tp = sum(prediction and label for prediction, label in zip(predictions, labels))
    fp = sum(prediction and not label for prediction, label in zip(predictions, labels))
    fn = sum(not prediction and label for prediction, label in zip(predictions, labels))
    tn = sum(not prediction and not label for prediction, label in zip(predictions, labels))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    false_positive_rate = fp / (fp + tn) if fp + tn else 0.0

    return EvaluationMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        false_positive_rate=false_positive_rate,
        total_flagged=tp + fp,
        total_evaluated=len(labels),
    )
