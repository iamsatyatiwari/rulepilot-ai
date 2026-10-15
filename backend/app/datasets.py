"""Versioned registry of the synthetic datasets available for evaluation."""

from __future__ import annotations

import csv
import gzip
import hashlib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.data import (
    CARD_SCENARIO_SEED,
    CARD_SCENARIO_SIZE,
    DEFAULT_DATASET_SEED,
    DEFAULT_DATASET_SIZE,
    PAYMENTS_SCENARIO_SEED,
    PAYMENTS_SCENARIO_SIZE,
    create_card_scenario_dataset,
    create_payments_scenario_dataset,
    create_synthetic_dataset,
)
from app.rules.models import Transaction, ruleable_fields

DEFAULT_DATASET_ID = "synthetic-v1"
SCENARIO_DATASET_ID = "card-scenario-v2"
PAYMENTS_DATASET_ID = "payments-scenario-v3"
SPARKOV_DATASET_ID = "sparkov-cards-v1"
SPARKOV_FILE = Path(__file__).parent / "data_files" / "sparkov-cards-v1.csv.gz"
SPARKOV_SHA256 = "fc34c63754f0c4c4041e14ba5ab63fb37a7f1f08f1cde9ece5714a96c21c7923"
SPARKOV_SIZE = 74740
# Dataset used by investigations and scheduled ingestion unless a request names another.
INVESTIGATION_DATASET_ID = PAYMENTS_DATASET_ID


class DatasetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    version: str
    generator_seed: int
    size: int
    synthetic: bool = True
    description: str
    limitations: str


DATASETS: dict[str, DatasetInfo] = {
    DEFAULT_DATASET_ID: DatasetInfo(
        dataset_id=DEFAULT_DATASET_ID,
        version="1.0.0",
        generator_seed=DEFAULT_DATASET_SEED,
        size=DEFAULT_DATASET_SIZE,
        description="Small synthetic fixture with four numeric features and a noisy risk process.",
        limitations=(
            "120 records with a 41% synthetic fraud rate; labels come from fixed feature "
            "thresholds. Illustrative only."
        ),
    ),
    SCENARIO_DATASET_ID: DatasetInfo(
        dataset_id=SCENARIO_DATASET_ID,
        version="2.0.0",
        generator_seed=CARD_SCENARIO_SEED,
        size=CARD_SCENARIO_SIZE,
        description=(
            "Synthetic card-payments scenario (~3% fraud) with velocity, decline, and "
            "card-present features, including a deliberately injected card-testing pattern."
        ),
        limitations=(
            "Fully synthetic. The card-testing pattern was injected to demonstrate how the "
            "workflow surfaces a coverage gap; results do not measure real-world detection."
        ),
    ),
    PAYMENTS_DATASET_ID: DatasetInfo(
        dataset_id=PAYMENTS_DATASET_ID,
        version="3.0.0",
        generator_seed=PAYMENTS_SCENARIO_SEED,
        size=PAYMENTS_SCENARIO_SIZE,
        description=(
            "Synthetic payments scenario (~3.4% fraud) with velocity, decline, card-present, "
            "time-of-day, device, SIM-change, credential-reset, and new-payee features. Three "
            "fraud modes: high-value misuse, injected card testing, and injected SIM-swap "
            "account takeover."
        ),
        limitations=(
            "Fully synthetic. The card-testing and SIM-swap account-takeover patterns were "
            "injected to demonstrate how the workflow surfaces coverage gaps, and legitimate "
            "look-alikes were added for each; results do not measure real-world detection."
        ),
    ),
    SPARKOV_DATASET_ID: DatasetInfo(
        dataset_id=SPARKOV_DATASET_ID,
        version="1.0.0",
        generator_seed=2026,
        size=SPARKOV_SIZE,
        description=(
            "Card transactions simulated by the independent, MIT-licensed Sparkov generator "
            "(200 customer profiles, six months, ~2.2% fraud in bursts on compromised cards). "
            "Features derived per card: amount, hour, card present, distance from home, 1h/24h "
            "velocity, and first payment to a merchant."
        ),
        limitations=(
            "Simulated, not real customer data, but the fraud behaviour was not designed by the "
            "RulePilot team. No device, SIM, decline, or account-age fields, so advisories that "
            "need them are not testable here. See app/data_files/NOTICE.md for provenance."
        ),
    ),
}


@lru_cache(maxsize=None)
def _load(dataset_id: str) -> tuple[Transaction, ...]:
    if dataset_id == DEFAULT_DATASET_ID:
        return tuple(create_synthetic_dataset())
    if dataset_id == SCENARIO_DATASET_ID:
        return tuple(create_card_scenario_dataset())
    if dataset_id == PAYMENTS_DATASET_ID:
        return tuple(create_payments_scenario_dataset())
    if dataset_id == SPARKOV_DATASET_ID:
        return tuple(_load_sparkov())
    raise KeyError(dataset_id)


def _load_sparkov() -> list[Transaction]:
    """Read the versioned Sparkov-derived file after checking its SHA-256."""
    raw = SPARKOV_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPARKOV_SHA256:
        raise ValueError(f"{SPARKOV_FILE.name} does not match its recorded SHA-256")
    rows = csv.DictReader(gzip.decompress(raw).decode("utf-8").splitlines())
    return [
        Transaction(
            transaction_id=row["transaction_id"],
            amount=float(row["amount"]),
            hour_of_day=int(row["hour_of_day"]),
            card_present=int(row["card_present"]),
            distance_from_home_km=float(row["distance_from_home_km"]),
            transactions_1h=int(row["transactions_1h"]),
            transactions_24h=int(row["transactions_24h"]),
            new_payee=int(row["new_payee"]),
            ground_truth_fraud=row["ground_truth_fraud"] == "1",
        )
        for row in rows
    ]


def get_dataset(dataset_id: str = DEFAULT_DATASET_ID) -> tuple[DatasetInfo, list[Transaction]]:
    """Return dataset metadata and a fresh list of its records."""
    if dataset_id not in DATASETS:
        raise KeyError(dataset_id)
    return DATASETS[dataset_id], list(_load(dataset_id))


def populated_fields(records: list[Transaction]) -> list[str]:
    """Return ruleable fields that have a value on every record of a dataset."""
    return sorted(
        field
        for field in ruleable_fields()
        if records and all(getattr(row, field) is not None for row in records)
    )
