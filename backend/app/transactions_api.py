"""HTTP endpoints that stand in for a bank's transaction feed (synthetic only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.baseline import BASELINE_RULE
from app.data import DEMO_FEED_MAX, create_demo_feed
from app.governance import GovernanceStore
from app.investigations_api import get_store
from app.rules.models import Transaction
from app.scoring import TransactionScore, score_transaction

router = APIRouter(prefix="/api/v1")


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction: Transaction


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: Annotated[int, Field(ge=1, le=DEMO_FEED_MAX)] = 20
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = 1


class FeedItem(BaseModel):
    transaction: Transaction
    synthetic_fraud: StrictBool
    score: TransactionScore


class FeedSummary(BaseModel):
    transactions: int
    synthetic_fraud: int
    flagged_by_active_rules: int
    fraud_caught_by_active_rules: int
    fraud_caught_only_in_shadow: int
    fraud_missed_by_all_rules: int
    legitimate_flagged_by_active_rules: int
    legitimate_flagged_only_in_shadow: int
    shadow_rules: int


class SimulateResponse(BaseModel):
    seed: int
    disclaimer: str
    summary: FeedSummary
    items: list[FeedItem]


@router.post("/transactions/score", response_model=TransactionScore, tags=["transactions"])
def score(request: ScoreRequest, store: GovernanceStore = Depends(get_store)) -> TransactionScore:
    """Score one transaction: active rules decide; approved rules are reported in shadow mode."""
    transaction = request.transaction.model_copy(update={"ground_truth_fraud": None})
    return score_transaction(transaction, [BASELINE_RULE], store.catalog())


@router.post("/transactions/simulate", response_model=SimulateResponse, tags=["transactions"])
def simulate(request: SimulateRequest, store: GovernanceStore = Depends(get_store)) -> SimulateResponse:
    """Generate a mock bank feed of fresh synthetic transactions and score each one."""
    try:
        feed = create_demo_feed(request.count, request.seed)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    shadow = store.catalog()
    items = []
    for transaction in feed:
        label = bool(transaction.ground_truth_fraud)
        # The scorer never sees the label; it is attached afterwards for the demo summary.
        result = score_transaction(transaction.model_copy(update={"ground_truth_fraud": None}), [BASELINE_RULE], shadow)
        items.append(FeedItem(transaction=transaction, synthetic_fraud=label, score=result))

    fraud = [item for item in items if item.synthetic_fraud]
    legit = [item for item in items if not item.synthetic_fraud]
    summary = FeedSummary(
        transactions=len(items),
        synthetic_fraud=len(fraud),
        flagged_by_active_rules=sum(item.score.decision == "flag" for item in items),
        fraud_caught_by_active_rules=sum(item.score.decision == "flag" for item in fraud),
        fraud_caught_only_in_shadow=sum(item.score.caught_only_in_shadow for item in fraud),
        fraud_missed_by_all_rules=sum(
            item.score.decision == "allow" and not item.score.shadow_flagged_by for item in fraud
        ),
        legitimate_flagged_by_active_rules=sum(item.score.decision == "flag" for item in legit),
        legitimate_flagged_only_in_shadow=sum(item.score.caught_only_in_shadow for item in legit),
        shadow_rules=len(shadow),
    )
    return SimulateResponse(
        seed=request.seed,
        disclaimer=(
            "Mock bank feed: fresh synthetic transactions with fraud deliberately over-represented "
            "(about 40%) for demonstration. Labels are synthetic and are not shown to the rules."
        ),
        summary=summary,
        items=items,
    )
