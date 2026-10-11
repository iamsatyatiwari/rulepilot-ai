"""Versioned HTTP endpoints for rules, evaluation, and discovery."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.baseline import BASELINE_RULE
from app.data import (
    DEFAULT_DATASET_SEED,
    DEFAULT_SPLIT_SEED,
    create_synthetic_dataset,
    sample_by_id,
    stratified_train_validation_test_split,
)
from app.discovery import DiscoveryReport, run_discovery
from app.evaluation import EvaluationMetrics, calculate_metrics
from app.rules.engine import evaluate_rule
from app.rules.models import Rule, Transaction

router = APIRouter(prefix="/api/v1")
SYNTHETIC_TRANSACTIONS = create_synthetic_dataset(seed=DEFAULT_DATASET_SEED)


class RuleListResponse(BaseModel):
    count: int
    items: list[Rule]


class EvaluateRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: Rule
    transaction_ids: list[StrictStr] | None = Field(default=None, max_length=500)


class Prediction(BaseModel):
    transaction_id: str
    flagged: bool


class EvaluateRuleResponse(BaseModel):
    rule_id: str
    predictions: list[Prediction]
    metrics: EvaluationMetrics


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_rule: Rule
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = DEFAULT_SPLIT_SEED


class BacktestResponse(BaseModel):
    evaluated_split: str
    baseline_rule: Rule
    candidate_rule: Rule
    baseline_metrics: EvaluationMetrics
    candidate_metrics: EvaluationMetrics
    fraud_missed_by_baseline: list[str]


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = DEFAULT_SPLIT_SEED


@router.get("/rules", response_model=RuleListResponse, tags=["rules"])
def list_rules() -> RuleListResponse:
    """List the documented baseline rule available in this milestone."""
    return RuleListResponse(count=1, items=[BASELINE_RULE])


@router.post("/rules/evaluate", response_model=EvaluateRuleResponse, tags=["rules"])
def evaluate_sample(request: EvaluateRuleRequest) -> EvaluateRuleResponse:
    """Evaluate a supplied rule on synthetic records without returning features."""
    if request.rule.rule_id == BASELINE_RULE.rule_id:
        raise HTTPException(status_code=409, detail="rule_id is already used by the baseline rule")
    try:
        records = sample_by_id(SYNTHETIC_TRANSACTIONS, request.transaction_ids)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"unknown_transaction_ids": error.args[0]}) from error

    predictions = [evaluate_rule(request.rule, record) for record in records]
    labels = [bool(record.ground_truth_fraud) for record in records]
    return EvaluateRuleResponse(
        rule_id=request.rule.rule_id,
        predictions=[
            Prediction(transaction_id=record.transaction_id or "", flagged=flagged)
            for record, flagged in zip(records, predictions)
        ],
        metrics=calculate_metrics(predictions, labels),
    )


@router.post("/backtests/run", response_model=BacktestResponse, tags=["backtests"])
def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """Compare baseline and supplied rule on the deterministic held-out test split."""
    if request.candidate_rule.rule_id == BASELINE_RULE.rule_id:
        raise HTTPException(status_code=409, detail="candidate rule_id must be unique")
    _, _, test = stratified_train_validation_test_split(SYNTHETIC_TRANSACTIONS, request.seed)
    labels = [bool(record.ground_truth_fraud) for record in test]
    baseline_predictions = [evaluate_rule(BASELINE_RULE, record) for record in test]
    candidate_predictions = [evaluate_rule(request.candidate_rule, record) for record in test]
    missed = [
        record.transaction_id or ""
        for record, predicted, label in zip(test, baseline_predictions, labels)
        if label and not predicted
    ]
    return BacktestResponse(
        evaluated_split="test",
        baseline_rule=BASELINE_RULE,
        candidate_rule=request.candidate_rule,
        baseline_metrics=calculate_metrics(baseline_predictions, labels),
        candidate_metrics=calculate_metrics(candidate_predictions, labels),
        fraud_missed_by_baseline=missed,
    )


@router.post("/rules/discover", response_model=DiscoveryReport, tags=["discovery"])
def discover_rules(
    request: DiscoveryRequest | None = None,
    seed: Annotated[int | None, Query(ge=0, le=2**32 - 1)] = None,
) -> DiscoveryReport:
    """Discover thresholds from train, select on validation, and test once."""
    chosen_seed = seed if seed is not None else request.seed if request else DEFAULT_SPLIT_SEED
    return run_discovery(SYNTHETIC_TRANSACTIONS, chosen_seed)


def get_sample_transactions() -> list[Transaction]:
    """Return a copy of the synthetic fixture for backend use and tests."""
    return list(SYNTHETIC_TRANSACTIONS)
