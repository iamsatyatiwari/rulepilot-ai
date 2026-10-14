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


CARD_SCENARIO_SEED = 2027
CARD_SCENARIO_SIZE = 6000


def create_card_scenario_dataset(
    size: int = CARD_SCENARIO_SIZE, seed: int = CARD_SCENARIO_SEED
) -> list[Transaction]:
    """Create a larger synthetic card-payments scenario with a documented injected pattern.

    Roughly 97% of records are legitimate. Two synthetic fraud modes are mixed in:
    high-value misuse far from home (about 1.5%) and a card-testing burst pattern
    (about 1.5%: very small card-not-present amounts, high one-hour velocity and
    repeated declines). Legitimate look-alikes (small-value bursts such as
    top-ups, occasional declines) are included so no rule is perfect. The
    card-testing mode is injected deliberately so the workflow can show what a
    detected coverage gap looks like; it is not evidence about real traffic.
    """
    if size < 0:
        raise ValueError("size must be non-negative")
    randomizer = random.Random(seed)
    rows: list[Transaction] = []
    for index in range(size):
        draw = randomizer.random()
        if draw < 0.015:
            # Synthetic high-value misuse.
            amount = round(randomizer.uniform(700, 4200), 2)
            account_age_days = randomizer.randint(1, 2400)
            transactions_24h = randomizer.randint(1, 8)
            transactions_1h = randomizer.randint(0, 3)
            declined = randomizer.choice([0, 0, 0, 1, 2])
            distance = round(randomizer.uniform(120, 3000), 2)
            card_present = randomizer.choice([0, 0, 1])
            is_fraud = True
        elif draw < 0.03:
            # Injected synthetic card-testing pattern.
            amount = round(randomizer.uniform(0.5, 25), 2)
            account_age_days = randomizer.randint(1, 2400)
            transactions_1h = randomizer.randint(2, 18)
            transactions_24h = transactions_1h + randomizer.randint(0, 10)
            declined = randomizer.randint(1, 14)
            distance = round(randomizer.uniform(0, 900), 2)
            card_present = 0
            is_fraud = True
        else:
            amount = round(min(randomizer.lognormvariate(3.8, 1.0), 6000), 2)
            account_age_days = randomizer.randint(1, 3600)
            transactions_1h = randomizer.choice([0, 0, 0, 1, 1, 2])
            transactions_24h = transactions_1h + randomizer.randint(0, 6)
            declined = randomizer.choice([0] * 18 + [1, 2])
            distance = round(randomizer.expovariate(1 / 25), 2)
            card_present = 1 if randomizer.random() < 0.6 else 0
            look_alike = randomizer.random()
            if look_alike < 0.015:
                # Legitimate small-value bursts (top-ups, transit taps, subscriptions).
                amount = round(randomizer.uniform(1, 15), 2)
                transactions_1h = randomizer.randint(3, 8)
                transactions_24h = transactions_1h + randomizer.randint(0, 6)
                card_present = randomizer.choice([0, 1])
                declined = randomizer.choice([0, 0, 1, 1, 2, 3, 4])
            elif look_alike < 0.023:
                # Legitimate large purchases while travelling.
                amount = round(randomizer.uniform(900, 3500), 2)
                distance = round(randomizer.uniform(150, 2500), 2)
            is_fraud = False

        rows.append(
            Transaction(
                transaction_id=f"CSC-{index + 1:05d}",
                amount=amount,
                account_age_days=account_age_days,
                transactions_24h=transactions_24h,
                distance_from_home_km=distance,
                transactions_1h=transactions_1h,
                declined_attempts_24h=declined,
                card_present=card_present,
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
