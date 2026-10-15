"""HTTP endpoints for the mock bank (demo cards and scored payments)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.bank import DEMO_CARDS, MERCHANTS, DemoCard, Merchant, PaymentRequest, PaymentResult, process_payment
from app.governance import GovernanceStore
from app.investigations_api import get_store

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
