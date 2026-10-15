"""Versioned HTTP endpoints for rules, evaluation, and discovery."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.backtest import compare_on_split
from app.baseline import BASELINE_RULE
from app.data import DEFAULT_SPLIT_SEED, sample_by_id
from app.datasets import DATASETS, DEFAULT_DATASET_ID, DatasetInfo, get_dataset
from app.discovery import DiscoveryReport, run_discovery
from app.evaluation import EvaluationMetrics, calculate_metrics
from app.rules.engine import evaluate_rule
from app.rules.models import Rule, Transaction

router = APIRouter(prefix="/api/v1")
SYNTHETIC_TRANSACTIONS = get_dataset(DEFAULT_DATASET_ID)[1]
DatasetId = Literal["synthetic-v1", "card-scenario-v2", "payments-scenario-v3", "sparkov-cards-v1"]


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
    dataset_id: DatasetId = DEFAULT_DATASET_ID


class BacktestResponse(BaseModel):
    evaluated_split: str
    dataset_id: str
    baseline_rule: Rule
    candidate_rule: Rule
    baseline_metrics: EvaluationMetrics
    candidate_metrics: EvaluationMetrics
    fraud_missed_by_baseline: list[str]
    fraud_missed_by_candidate: list[str]
    combined_metrics: EvaluationMetrics
    fraud_missed_by_combined: list[str]


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = DEFAULT_SPLIT_SEED
    dataset_id: DatasetId = DEFAULT_DATASET_ID


class DatasetListResponse(BaseModel):
    count: int
    items: list[DatasetInfo]


@router.get("/datasets", response_model=DatasetListResponse, tags=["datasets"])
def list_datasets() -> DatasetListResponse:
    """List versioned synthetic datasets available for evaluation."""
    return DatasetListResponse(count=len(DATASETS), items=list(DATASETS.values()))


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
    _, records = get_dataset(request.dataset_id)
    comparison = compare_on_split(request.candidate_rule, records, request.seed, "test")
    return BacktestResponse(
        evaluated_split=comparison.evaluated_split,
        dataset_id=request.dataset_id,
        baseline_rule=BASELINE_RULE,
        candidate_rule=request.candidate_rule,
        baseline_metrics=comparison.baseline_metrics,
        candidate_metrics=comparison.candidate_metrics,
        fraud_missed_by_baseline=comparison.fraud_missed_by_baseline,
        fraud_missed_by_candidate=comparison.fraud_missed_by_candidate,
        combined_metrics=comparison.combined_metrics,
        fraud_missed_by_combined=comparison.fraud_missed_by_combined,
    )


@router.post("/rules/discover", response_model=DiscoveryReport, tags=["discovery"])
def discover_rules(
    request: DiscoveryRequest | None = None,
    seed: Annotated[int | None, Query(ge=0, le=2**32 - 1)] = None,
) -> DiscoveryReport:
    """Discover thresholds from train, select on validation, and test once."""
    chosen_seed = seed if seed is not None else request.seed if request else DEFAULT_SPLIT_SEED
    dataset_id = request.dataset_id if request else DEFAULT_DATASET_ID
    _, records = get_dataset(dataset_id)
    return run_discovery(records, chosen_seed)


def get_sample_transactions() -> list[Transaction]:
    """Return a copy of the synthetic fixture for backend use and tests."""
    return list(SYNTHETIC_TRANSACTIONS)
