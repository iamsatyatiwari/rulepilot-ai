"""Small, reproducible synthetic transactions for development and examples."""

from __future__ import annotations

import random

from app.rules.models import Transaction

DEFAULT_DATASET_SEED = 2026
DEFAULT_SPLIT_SEED = 41
DEFAULT_DATASET_SIZE = 120


def create_synthetic_dataset(
    size: int = DEFAULT_DATASET_SIZE, seed: int = DEFAULT_DATASET_SEED
) -> list[Transaction]:
    """Create synthetic-only records with probabilistic, known binary labels.

    Labels are sampled from a noisy risk process over generated numeric
    features. This is an illustrative fixture, not a model of real fraud.
    """
    if size < 0:
        raise ValueError("size must be non-negative")
    randomizer = random.Random(seed)
    rows: list[Transaction] = []
    for index in range(size):
        amount = round(randomizer.uniform(15, 2600), 2)
        account_age_days = randomizer.randint(1, 2400)
        transactions_24h = randomizer.randint(1, 12)
        distance_from_home_km = round(randomizer.uniform(0, 650), 2)

        risk = 0.015
        risk += 0.36 if amount > 900 else 0.0
        risk += 0.23 if account_age_days < 20 else 0.0
        risk += 0.19 if distance_from_home_km > 180 else 0.0
        risk += 0.12 if transactions_24h > 5 else 0.0
        is_fraud = randomizer.random() < min(risk, 0.92)

        rows.append(
            Transaction(
                transaction_id=f"SYN-{index + 1:04d}",
                amount=amount,
                account_age_days=account_age_days,
                transactions_24h=transactions_24h,
                distance_from_home_km=distance_from_home_km,
                ground_truth_fraud=is_fraud,
            )
        )
    return rows


def stratified_train_validation_test_split(
    transactions: list[Transaction], seed: int = DEFAULT_SPLIT_SEED
) -> tuple[list[Transaction], list[Transaction], list[Transaction]]:
    """Return deterministic 60/20/20 splits, stratified by known label."""
    randomizer = random.Random(seed)
    groups: dict[bool, list[Transaction]] = {False: [], True: []}
    for transaction in transactions:
        if transaction.ground_truth_fraud is None:
            raise ValueError("all dataset records must have a ground-truth label")
        groups[transaction.ground_truth_fraud].append(transaction)

    train: list[Transaction] = []
    validation: list[Transaction] = []
    test: list[Transaction] = []
    for label_group in groups.values():
        randomizer.shuffle(label_group)
        train_count = int(len(label_group) * 0.6)
        validation_count = int(len(label_group) * 0.2)
        train.extend(label_group[:train_count])
        validation.extend(label_group[train_count : train_count + validation_count])
        test.extend(label_group[train_count + validation_count :])

    randomizer.shuffle(train)
    randomizer.shuffle(validation)
    randomizer.shuffle(test)
    return train, validation, test


def sample_by_id(
    transactions: list[Transaction], transaction_ids: list[str] | None = None
) -> list[Transaction]:
    """Return requested synthetic records while preserving caller order."""
    if transaction_ids is None:
        return list(transactions)
    lookup = {row.transaction_id: row for row in transactions}
    if len(transaction_ids) != len(set(transaction_ids)):
        raise ValueError("transaction_ids must not contain duplicates")
    unknown = [transaction_id for transaction_id in transaction_ids if transaction_id not in lookup]
    if unknown:
        raise KeyError(unknown)
    return [lookup[transaction_id] for transaction_id in transaction_ids]
