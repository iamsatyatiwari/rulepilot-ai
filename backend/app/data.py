"""Small, reproducible synthetic transactions for development and examples."""

from __future__ import annotations

import random
from typing import Literal

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
            pattern: ScenarioPattern = "high_value_misuse"
        elif draw < 0.03:
            pattern = "card_testing"
        else:
            pattern = "legitimate"
        rows.append(_card_scenario_row(randomizer, pattern, f"CSC-{index + 1:05d}"))
    return rows


ScenarioPattern = Literal["high_value_misuse", "card_testing", "legitimate"]


def _card_scenario_row(randomizer: random.Random, pattern: ScenarioPattern, transaction_id: str) -> Transaction:
    """Draw one card-scenario record for a given pattern (shared by the dataset and the demo feed)."""
    if pattern == "high_value_misuse":
        # Synthetic high-value misuse.
        amount = round(randomizer.uniform(700, 4200), 2)
        account_age_days = randomizer.randint(1, 2400)
        transactions_24h = randomizer.randint(1, 8)
        transactions_1h = randomizer.randint(0, 3)
        declined = randomizer.choice([0, 0, 0, 1, 2])
        distance = round(randomizer.uniform(120, 3000), 2)
        card_present = randomizer.choice([0, 0, 1])
        is_fraud = True
    elif pattern == "card_testing":
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

    return Transaction(
        transaction_id=transaction_id,
        amount=amount,
        account_age_days=account_age_days,
        transactions_24h=transactions_24h,
        distance_from_home_km=distance,
        transactions_1h=transactions_1h,
        declined_attempts_24h=declined,
        card_present=card_present,
        ground_truth_fraud=is_fraud,
    )


PAYMENTS_SCENARIO_SEED = 2028
PAYMENTS_SCENARIO_SIZE = 30000
PAYMENTS_HIGH_VALUE_SHARE = 0.012
PAYMENTS_CARD_TESTING_SHARE = 0.012
PAYMENTS_ACCOUNT_TAKEOVER_SHARE = 0.010

PaymentsPattern = Literal["high_value_misuse", "card_testing", "account_takeover", "legitimate"]

# Relative weight of each local hour for legitimate activity (quiet overnight, busy daytime).
_DAYTIME_HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 9, 9, 10, 9, 9, 9, 9, 9, 8, 7, 6, 4, 3, 2]
# Fraud skews towards the night, when account holders are less likely to notice.
_NIGHT_SKEWED_HOUR_WEIGHTS = [6, 7, 7, 7, 6, 5, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 5, 6]


def create_payments_scenario_dataset(
    size: int = PAYMENTS_SCENARIO_SIZE, seed: int = PAYMENTS_SCENARIO_SEED
) -> list[Transaction]:
    """Create a larger synthetic payments scenario with three documented fraud modes.

    About 3.4% of records are fraud: high-value misuse (~1.2%), injected card
    testing (~1.2%), and an injected SIM-swap account-takeover pattern (~1.0%:
    a recent SIM change, a new device, credential resets, and a sizeable
    card-not-present payment to a new payee). Legitimate look-alikes are mixed
    in for every mode (small-value bursts, travel purchases, customers who just
    replaced their phone, first payments to a new payee) so no rule is perfect.
    The injected patterns exist so the workflow can show detectable coverage
    gaps; they are not evidence about real traffic.
    """
    if size < 0:
        raise ValueError("size must be non-negative")
    randomizer = random.Random(seed)
    rows: list[Transaction] = []
    for index in range(size):
        draw = randomizer.random()
        if draw < PAYMENTS_HIGH_VALUE_SHARE:
            pattern: PaymentsPattern = "high_value_misuse"
        elif draw < PAYMENTS_HIGH_VALUE_SHARE + PAYMENTS_CARD_TESTING_SHARE:
            pattern = "card_testing"
        elif draw < PAYMENTS_HIGH_VALUE_SHARE + PAYMENTS_CARD_TESTING_SHARE + PAYMENTS_ACCOUNT_TAKEOVER_SHARE:
            pattern = "account_takeover"
        else:
            pattern = "legitimate"
        rows.append(_payments_row(randomizer, pattern, f"PSC-{index + 1:05d}"))
    return rows


def _payments_row(randomizer: random.Random, pattern: PaymentsPattern, transaction_id: str) -> Transaction:
    """Draw one payments-scenario record: card-scenario features plus device, SIM, and payee signals."""
    if pattern == "account_takeover":
        # Injected synthetic SIM-swap account takeover: the attacker ports the
        # victim's number, resets credentials, and pays out from a new device.
        amount = round(randomizer.uniform(400, 6000), 2)
        account_age_days = randomizer.randint(90, 3600)
        transactions_1h = randomizer.randint(0, 2)
        transactions_24h = transactions_1h + randomizer.randint(0, 3)
        declined = randomizer.choice([0, 0, 0, 1])
        distance = round(randomizer.expovariate(1 / 60), 2)
        hour = randomizer.choices(range(24), weights=_NIGHT_SKEWED_HOUR_WEIGHTS)[0]
        new_device = 1 if randomizer.random() < 0.9 else 0
        days_since_sim_change = randomizer.randint(0, 3) if randomizer.random() < 0.85 else randomizer.randint(4, 10)
        credential_resets = randomizer.randint(1, 3) if randomizer.random() < 0.8 else 0
        new_payee = 1 if randomizer.random() < 0.9 else 0
        return Transaction(
            transaction_id=transaction_id,
            amount=amount,
            account_age_days=account_age_days,
            transactions_24h=transactions_24h,
            distance_from_home_km=distance,
            transactions_1h=transactions_1h,
            declined_attempts_24h=declined,
            card_present=0,
            hour_of_day=hour,
            new_device=new_device,
            days_since_sim_change=days_since_sim_change,
            credential_resets_24h=credential_resets,
            new_payee=new_payee,
            ground_truth_fraud=True,
        )

    base = _card_scenario_row(randomizer, pattern, transaction_id)
    days_since_sim_change = randomizer.randint(30, 2500)
    credential_resets = 0
    if pattern == "card_testing":
        hour = randomizer.choices(range(24), weights=_NIGHT_SKEWED_HOUR_WEIGHTS)[0]
        new_device = 1 if randomizer.random() < 0.6 else 0
        new_payee = 1 if randomizer.random() < 0.7 else 0
    elif pattern == "high_value_misuse":
        hour = randomizer.choices(range(24), weights=_NIGHT_SKEWED_HOUR_WEIGHTS)[0]
        new_device = 1 if randomizer.random() < 0.5 else 0
        new_payee = 1 if randomizer.random() < 0.6 else 0
        credential_resets = 1 if randomizer.random() < 0.1 else 0
    else:
        hour = randomizer.choices(range(24), weights=_DAYTIME_HOUR_WEIGHTS)[0]
        new_device = 1 if randomizer.random() < 0.04 else 0
        new_payee = 1 if randomizer.random() < 0.15 else 0
        credential_resets = 1 if randomizer.random() < 0.02 else 0
        look_alike = randomizer.random()
        if look_alike < 0.015:
            # Legitimate customers who just replaced or re-issued their SIM and phone.
            days_since_sim_change = randomizer.randint(0, 3)
            new_device = 1 if randomizer.random() < 0.8 else 0
            credential_resets = randomizer.randint(1, 2) if randomizer.random() < 0.4 else 0
        elif look_alike < 0.025:
            # Legitimate first-time sizeable payments (rent deposits, new suppliers).
            new_payee = 1
            base = base.model_copy(update={"amount": round(randomizer.uniform(500, 4000), 2), "card_present": 0})
    return base.model_copy(
        update={
            "hour_of_day": hour,
            "new_device": new_device,
            "days_since_sim_change": days_since_sim_change,
            "credential_resets_24h": credential_resets,
            "new_payee": new_payee,
        }
    )


DEMO_FEED_MAX = 50
DEMO_FEED_CARD_TESTING_SHARE = 0.22
DEMO_FEED_HIGH_VALUE_SHARE = 0.08
DEMO_FEED_ACCOUNT_TAKEOVER_SHARE = 0.10


def create_demo_feed(count: int, seed: int) -> list[Transaction]:
    """Create fresh synthetic transactions that stand in for a bank's live feed.

    Records are drawn with the same per-pattern distributions as
    ``payments-scenario-v3`` but from an independent random stream, so they are
    never records from any dataset split. Fraud is deliberately over-represented
    (about 22% card testing, 8% high-value misuse, 10% SIM-swap account takeover)
    so a short demo shows each pattern; this mix is not a realistic fraud rate.
    """
    if not 1 <= count <= DEMO_FEED_MAX:
        raise ValueError(f"count must be between 1 and {DEMO_FEED_MAX}")
    randomizer = random.Random(f"rulepilot-demo-feed:{seed}")
    rows: list[Transaction] = []
    for index in range(count):
        draw = randomizer.random()
        if draw < DEMO_FEED_CARD_TESTING_SHARE:
            pattern: PaymentsPattern = "card_testing"
        elif draw < DEMO_FEED_CARD_TESTING_SHARE + DEMO_FEED_HIGH_VALUE_SHARE:
            pattern = "high_value_misuse"
        elif draw < DEMO_FEED_CARD_TESTING_SHARE + DEMO_FEED_HIGH_VALUE_SHARE + DEMO_FEED_ACCOUNT_TAKEOVER_SHARE:
            pattern = "account_takeover"
        else:
            pattern = "legitimate"
        rows.append(_payments_row(randomizer, pattern, f"FEED-{seed}-{index + 1:03d}"))
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
