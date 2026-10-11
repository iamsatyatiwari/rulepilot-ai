import pytest

from app.evaluation import calculate_metrics


def test_confusion_matrix_and_metrics():
    metrics = calculate_metrics(
        predictions=[True, True, False, False],
        labels=[True, False, True, False],
    )
    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.true_negatives == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.total_flagged == 2
    assert metrics.total_evaluated == 4


def test_zero_denominators_use_zero_convention():
    metrics = calculate_metrics([False, False], [False, False])
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.false_positive_rate == 0.0
    assert metrics.total_flagged == 0
    assert metrics.total_evaluated == 2
    empty = calculate_metrics([], [])
    assert empty.total_evaluated == 0


def test_misaligned_or_non_boolean_inputs_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        calculate_metrics([True], [True, False])
    with pytest.raises(ValueError, match="only booleans"):
        calculate_metrics([1], [True])
