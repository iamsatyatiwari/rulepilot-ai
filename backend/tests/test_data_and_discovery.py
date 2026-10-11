from app.data import (
    create_synthetic_dataset,
    stratified_train_validation_test_split,
)
from app.discovery import discover_candidate, run_discovery


def test_synthetic_data_is_reproducible_and_labeled():
    first = create_synthetic_dataset(size=120, seed=7)
    second = create_synthetic_dataset(size=120, seed=7)
    assert [row.model_dump() for row in first] == [row.model_dump() for row in second]
    assert {row.ground_truth_fraud for row in first} == {True, False}


def test_split_is_reproducible_stratified_and_disjoint(synthetic_transactions):
    first = stratified_train_validation_test_split(synthetic_transactions, seed=8)
    second = stratified_train_validation_test_split(synthetic_transactions, seed=8)
    ids = [{row.transaction_id for row in split} for split in first]
    assert [[row.transaction_id for row in split] for split in first] == [
        [row.transaction_id for row in split] for split in second
    ]
    assert ids[0].isdisjoint(ids[1])
    assert ids[0].isdisjoint(ids[2])
    assert ids[1].isdisjoint(ids[2])
    assert len(set.union(*ids)) == len(synthetic_transactions)


def test_discovery_candidate_threshold_comes_from_training_only(synthetic_transactions):
    training, validation, _ = stratified_train_validation_test_split(
        synthetic_transactions, seed=41
    )
    candidate, validation_metrics, count, reason = discover_candidate(
        training, validation, seed=41
    )
    assert reason is None
    assert count > 0
    assert candidate is not None
    assert validation_metrics is not None
    condition = candidate.conditions[0]
    training_values = sorted({getattr(row, condition.field) for row in training})
    assert condition.value not in training_values
    assert min(training_values) < condition.value < max(training_values)
    assert validation_metrics.total_evaluated == len(validation)


def test_discovery_is_reproducible_and_reports_test_evidence(synthetic_transactions):
    first = run_discovery(synthetic_transactions, seed=41)
    second = run_discovery(synthetic_transactions, seed=41)
    assert first.status == "candidate_found"
    assert first.candidate_rule is not None and second.candidate_rule is not None
    assert first.candidate_rule.rule_id == second.candidate_rule.rule_id
    assert first.candidate_rule.conditions == second.candidate_rule.conditions
    assert first.validation_metrics == second.validation_metrics
    assert first.candidate_test_metrics == second.candidate_test_metrics
    assert first.test_count > 0
    assert first.baseline_test_metrics is not None
    assert first.candidate_test_metrics is not None


def test_insufficient_data_returns_explicit_result():
    report = run_discovery(create_synthetic_dataset(size=3))
    assert report.status == "insufficient_evidence"
    assert report.candidate_rule is None
    assert report.reason


def test_test_labels_do_not_influence_candidate_selection(monkeypatch, synthetic_transactions):
    import app.discovery as discovery

    training, validation, test = stratified_train_validation_test_split(
        synthetic_transactions, seed=41
    )
    first_candidate, first_validation_metrics, _, _ = discover_candidate(
        training, validation, seed=41
    )
    flipped_test = [
        row.model_copy(update={"ground_truth_fraud": not row.ground_truth_fraud})
        for row in test
    ]
    monkeypatch.setattr(
        discovery,
        "stratified_train_validation_test_split",
        lambda _rows, _seed: (training, validation, test),
    )
    first_report = discovery.run_discovery(synthetic_transactions, seed=41)
    monkeypatch.setattr(
        discovery,
        "stratified_train_validation_test_split",
        lambda _rows, _seed: (training, validation, flipped_test),
    )
    second_report = discovery.run_discovery(synthetic_transactions, seed=41)

    assert first_candidate is not None and second_report.candidate_rule is not None
    assert first_report.candidate_rule is not None
    assert first_report.candidate_rule.conditions == second_report.candidate_rule.conditions
    assert first_report.validation_metrics == first_validation_metrics
    assert first_report.candidate_test_metrics != second_report.candidate_test_metrics


def test_selected_candidate_is_evaluated_once_on_held_out_records(
    monkeypatch, synthetic_transactions
):
    import app.discovery as discovery

    training, validation, test = stratified_train_validation_test_split(
        synthetic_transactions, seed=41
    )
    monkeypatch.setattr(
        discovery,
        "stratified_train_validation_test_split",
        lambda _rows, _seed: (training, validation, test),
    )
    original_predictions = discovery._predictions
    test_calls = []

    def track_predictions(rule, records):
        if [row.transaction_id for row in records] == [row.transaction_id for row in test]:
            test_calls.append(rule.rule_id)
        return original_predictions(rule, records)

    monkeypatch.setattr(discovery, "_predictions", track_predictions)
    report = discovery.run_discovery(synthetic_transactions, seed=41)
    assert report.candidate_rule is not None
    assert test_calls.count(report.candidate_rule.rule_id) == 1
