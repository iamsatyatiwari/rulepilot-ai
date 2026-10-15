"""Versioned registry of the synthetic datasets available for evaluation."""

from __future__ import annotations

from functools import lru_cache

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
}


@lru_cache(maxsize=None)
def _load(dataset_id: str) -> tuple[Transaction, ...]:
    if dataset_id == DEFAULT_DATASET_ID:
        return tuple(create_synthetic_dataset())
    if dataset_id == SCENARIO_DATASET_ID:
        return tuple(create_card_scenario_dataset())
    if dataset_id == PAYMENTS_DATASET_ID:
        return tuple(create_payments_scenario_dataset())
    raise KeyError(dataset_id)


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
