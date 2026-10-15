"""HTTP endpoints for the mock bank (demo cards and scored payments)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.bank import DEMO_CARDS, MERCHANTS, DemoCard, Merchant, PaymentRequest, PaymentResult, card, derive_features, merchant, process_payment
from app.governance import GovernanceStore
from app.investigations_api import get_store
from app.rule_lab import TestCase, TestCaseInput, case_store

router = APIRouter(prefix="/api/v1/bank", tags=["mock bank"])


class BankCatalog(BaseModel):
    cards: list[DemoCard]
    merchants: list[Merchant]
    disclaimer: str


@router.get("/catalog", response_model=BankCatalog)
def catalog() -> BankCatalog:
    return BankCatalog(
        cards=list(DEMO_CARDS),
        merchants=list(MERCHANTS),
        disclaimer="Demo bank with fictional cardholders and cards. No real payments are made.",
    )


@router.post("/payments", response_model=PaymentResult)
def pay(request: PaymentRequest, store: GovernanceStore = Depends(get_store)) -> PaymentResult:
    """Score a demo payment: the baseline and every approved rule are active and decide."""
    try:
        return process_payment(request, store.catalog())
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"unknown card or merchant: {error.args[0]}") from error


class FraudReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment: PaymentRequest
    note: Annotated[StrictStr, Field(max_length=300)] = ""


@router.post("/reports", response_model=TestCase, status_code=201)
def report_fraud(request: FraudReportRequest, store: GovernanceStore = Depends(get_store)) -> TestCase:
    """A customer reports a payment as fraud. Features are re-derived on the server, not taken from the browser."""
    try:
        holder, shop = card(request.payment.card_id), merchant(request.payment.merchant_id)
        features = derive_features(request.payment)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"unknown card or merchant: {error.args[0]}") from error
    case = TestCaseInput(
        name=f"Customer report: {shop.name}, {request.payment.amount:.2f}",
        transaction=features,
        expected="fraud",
        note=request.note,
        created_by=f"{holder.holder} (card {holder.last4})",
    )
    try:
        return case_store(store.backend).add(case, source="customer_report")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
