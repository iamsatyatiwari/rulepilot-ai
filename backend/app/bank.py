"""Mock bank: demo cards whose payments are scored by the rule engine.

This is a demonstration surface, not a payment system. The browser keeps each
demo card's recent activity and sends it with every payment; the server
derives the rule features from that history (velocity, declines, new payee,
SIM change, credential resets), then scores the payment exactly as the
transaction monitor does: the baseline and every approved rule are active and decide.
Keeping the server stateless means any Cloud Run instance can answer.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.baseline import BASELINE_RULE
from app.governance import CatalogEntry
from app.rules.models import Transaction
from app.scoring import TransactionScore, score_transaction

MAX_HISTORY = 200
Channel = Literal["online", "in_store"]
SecurityEventType = Literal["sim_change", "credential_reset", "new_device_login"]


class DemoCard(BaseModel):
    card_id: str
    holder: str
    label: str
    last4: str
    account_age_days: int
    days_since_sim_change: int
    description: str


class Merchant(BaseModel):
    merchant_id: str
    name: str
    channel: Channel
    distance_from_home_km: float
    typical_amount: float


DEMO_CARDS: tuple[DemoCard, ...] = (
    DemoCard(card_id="card-asha", holder="Asha Rao", label="Everyday debit", last4="1001",
             account_age_days=2140, days_since_sim_change=812,
             description="Long-standing customer; groceries, fuel, and the odd online order."),
    DemoCard(card_id="card-ben", holder="Ben Ortiz", label="Online shopper credit", last4="2002",
             account_age_days=960, days_since_sim_change=430,
             description="Shops online a lot; good for showing card-testing bursts."),
    DemoCard(card_id="card-chen", holder="Chen Wei", label="Premium current account", last4="3003",
             account_age_days=3120, days_since_sim_change=1290,
             description="High balance; target of the SIM-swap takeover scenario."),
)

MERCHANTS: tuple[Merchant, ...] = (
    Merchant(merchant_id="m-grocer", name="Corner Grocer", channel="in_store", distance_from_home_km=2.5, typical_amount=46.2),
    Merchant(merchant_id="m-fuel", name="City Fuel", channel="in_store", distance_from_home_km=6.0, typical_amount=58.0),
    Merchant(merchant_id="m-books", name="Paper Trail Books (online)", channel="online", distance_from_home_km=0.0, typical_amount=24.9),
    Merchant(merchant_id="m-giftcard", name="QuickGift Cards (online)", channel="online", distance_from_home_km=0.0, typical_amount=2.0),
    Merchant(merchant_id="m-electronics", name="MegaTech Electronics", channel="online", distance_from_home_km=0.0, typical_amount=1899.0),
    Merchant(merchant_id="m-hotel", name="Harbour Hotel, Lisbon", channel="in_store", distance_from_home_km=1840.0, typical_amount=640.0),
    Merchant(merchant_id="m-transfer", name="Transfer to new payee: J. Doe", channel="online", distance_from_home_km=0.0, typical_amount=1240.0),
)

_CARDS = {card.card_id: card for card in DEMO_CARDS}
_MERCHANTS = {merchant.merchant_id: merchant for merchant in MERCHANTS}


class HistoryItem(BaseModel):
    """One earlier payment attempt on the card, as the browser recorded it."""

    model_config = ConfigDict(extra="forbid")

    at: AwareDatetime
    merchant_id: Annotated[StrictStr, Field(max_length=64)]
    amount: Annotated[float, Field(ge=0, le=1_000_000)]
    declined: StrictBool = False


class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: AwareDatetime
    type: SecurityEventType


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: Annotated[StrictStr, Field(max_length=64)]
    merchant_id: Annotated[StrictStr, Field(max_length=64)]
    amount: Annotated[float, Field(gt=0, le=1_000_000)]
    at: AwareDatetime
    cvv_correct: StrictBool = True
    new_device: StrictBool = False
    history: Annotated[list[HistoryItem], Field(max_length=MAX_HISTORY)] = []
    security_events: Annotated[list[SecurityEvent], Field(max_length=50)] = []


class PaymentResult(BaseModel):
    outcome: Literal["approved", "held_for_review", "declined_by_issuer"]
    explanation: str
    shadow_summary: str
    features: Transaction
    score: TransactionScore


def card(card_id: str) -> DemoCard:
    if card_id not in _CARDS:
        raise KeyError(card_id)
    return _CARDS[card_id]


def merchant(merchant_id: str) -> Merchant:
    if merchant_id not in _MERCHANTS:
        raise KeyError(merchant_id)
    return _MERCHANTS[merchant_id]


def derive_features(request: PaymentRequest) -> Transaction:
    """Turn a payment plus the card's recent activity into rule features.

    Only history and events at or before the payment time count.
    """
    profile = card(request.card_id)
    shop = merchant(request.merchant_id)
    now = request.at
    past = [item for item in request.history if item.at <= now]
    events = [event for event in request.security_events if event.at <= now]
    last_hour = [item for item in past if item.at > now - timedelta(hours=1)]
    last_day = [item for item in past if item.at > now - timedelta(hours=24)]
    sim_changes = [event.at for event in events if event.type == "sim_change"]
    days_since_sim = (
        max(0, (now - max(sim_changes)).days) if sim_changes else profile.days_since_sim_change
    )
    recent_login_from_new_device = any(
        event.type == "new_device_login" and event.at > now - timedelta(hours=24) for event in events
    )
    return Transaction(
        transaction_id=f"BANK-{profile.last4}-{len(past) + 1:03d}",
        amount=round(request.amount, 2),
        account_age_days=profile.account_age_days,
        transactions_24h=len(last_day),
        transactions_1h=len(last_hour),
        distance_from_home_km=shop.distance_from_home_km,
        declined_attempts_24h=sum(item.declined for item in last_day),
        card_present=1 if shop.channel == "in_store" else 0,
        hour_of_day=now.hour,
        new_device=1 if request.new_device or recent_login_from_new_device else 0,
        days_since_sim_change=days_since_sim,
        credential_resets_24h=sum(
            event.type == "credential_reset" and event.at > now - timedelta(hours=24) for event in events
        ),
        new_payee=0 if any(item.merchant_id == shop.merchant_id for item in past) else 1,
    )


def process_payment(request: PaymentRequest, approved_entries: list[CatalogEntry]) -> PaymentResult:
    features = derive_features(request)
    score = score_transaction(features, [BASELINE_RULE], [], approved_entries)
    if not request.cvv_correct:
        outcome: Literal["approved", "held_for_review", "declined_by_issuer"] = "declined_by_issuer"
        explanation = "Declined by the card issuer: the security code did not match."
    elif score.decision == "flag":
        outcome = "held_for_review"
        explanation = f"Held for review by active rule {', '.join(score.decided_by)}."
        if score.caught_only_by_approved:
            explanation = (
                f"Held for review by approved RulePilot rule {', '.join(score.approved_flagged_by)}; "
                "the original rule alone would have approved it."
            )
    else:
        outcome = "approved"
        explanation = "Approved: no active rule flagged this payment."
    # Field name kept for compatibility; it now summarizes the approved (active) rules.
    if score.approved_flagged_by:
        shadow_summary = f"Approved RulePilot rule {', '.join(score.approved_flagged_by)} flagged this payment."
    elif approved_entries:
        shadow_summary = "No approved RulePilot rule flagged this payment."
    else:
        shadow_summary = "No RulePilot rules have been approved yet."
    return PaymentResult(
        outcome=outcome, explanation=explanation, shadow_summary=shadow_summary, features=features, score=score
    )
