from datetime import datetime, timedelta, timezone

import pytest

from app.bank import PaymentRequest, derive_features, process_payment
from test_transactions import approve_card_testing_rule, client, store  # noqa: F401 (fixtures)

NOW = datetime(2026, 10, 15, 2, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def payment(**overrides):
    body = {"card_id": "card-ben", "merchant_id": "m-giftcard", "amount": 2.0, "at": NOW.isoformat()}
    body.update(overrides)
    return body


def attempts(count, minutes_apart=4, declined_every=2):
    return [
        {
            "at": (NOW - timedelta(minutes=minutes_apart * (index + 1))).isoformat(),
            "merchant_id": "m-giftcard",
            "amount": 1.5,
            "declined": index % declined_every == 0,
        }
        for index in range(count)
    ]


def test_features_come_from_recent_history_and_local_time():
    history = attempts(4) + [{"at": (NOW - timedelta(hours=30)).isoformat(), "merchant_id": "m-books", "amount": 20.0}]
    features = derive_features(PaymentRequest.model_validate(payment(history=history)))
    assert features.transactions_1h == 4
    assert features.transactions_24h == 4
    assert features.declined_attempts_24h == 2
    assert features.card_present == 0 and features.new_payee == 0
    assert features.hour_of_day == 2  # the customer's local hour, not UTC
    assert features.days_since_sim_change == 430


def test_future_history_and_old_events_are_ignored():
    future = [{"at": (NOW + timedelta(minutes=5)).isoformat(), "merchant_id": "m-giftcard", "amount": 1.0}]
    events = [{"at": (NOW - timedelta(days=3)).isoformat(), "type": "credential_reset"}]
    features = derive_features(PaymentRequest.model_validate(payment(history=future, security_events=events)))
    assert features.transactions_1h == 0 and features.new_payee == 1
    assert features.credential_resets_24h == 0


def test_sim_swap_events_change_the_takeover_features():
    events = [
        {"at": (NOW - timedelta(hours=5)).isoformat(), "type": "sim_change"},
        {"at": (NOW - timedelta(hours=4)).isoformat(), "type": "credential_reset"},
        {"at": (NOW - timedelta(hours=3)).isoformat(), "type": "new_device_login"},
    ]
    request = payment(card_id="card-chen", merchant_id="m-transfer", amount=1240.0, security_events=events)
    features = derive_features(PaymentRequest.model_validate(request))
    assert features.days_since_sim_change == 0
    assert features.credential_resets_24h == 1
    assert features.new_device == 1 and features.new_payee == 1


def test_baseline_holds_large_payments_and_issuer_declines_bad_cvv():
    big = process_payment(PaymentRequest.model_validate(payment(merchant_id="m-electronics", amount=1899.0)), [])
    assert big.outcome == "held_for_review" and big.score.decided_by == ["RP-BASELINE-001"]
    bad_cvv = process_payment(PaymentRequest.model_validate(payment(cvv_correct=False)), [])
    assert bad_cvv.outcome == "declined_by_issuer"
    assert "No RulePilot rules" in bad_cvv.shadow_summary


def test_approved_rule_blocks_the_card_testing_burst(client, store):  # noqa: F811
    rule_id = approve_card_testing_rule(client)
    first = client.post("/api/v1/bank/payments", json=payment()).json()
    assert first["outcome"] == "approved" and first["score"]["approved_flagged_by"] == []
    burst = client.post("/api/v1/bank/payments", json=payment(history=attempts(5))).json()
    assert burst["outcome"] == "held_for_review"  # approval activates the rule
    assert burst["score"]["approved_flagged_by"] == [rule_id] and burst["score"]["caught_only_by_approved"]
    assert rule_id in burst["explanation"] and rule_id in burst["shadow_summary"]


def test_rejecting_an_approved_rule_deactivates_it(client, store):  # noqa: F811
    rule_id = approve_card_testing_rule(client)
    investigation_id = store.catalog()[0].investigation_id
    reject = client.post(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "reject", "reviewer": "analyst", "comment": "Too many false alarms."},
    )
    assert reject.status_code == 200 and reject.json()["activation"] == "not_activated"
    burst = client.post("/api/v1/bank/payments", json=payment(history=attempts(5))).json()
    assert burst["outcome"] == "approved" and rule_id not in burst["score"]["decided_by"]
    events = [event["event"] for event in client.get("/api/v1/audit").json()]
    assert "rule_removed_from_catalog" in events


def test_bank_catalog_and_input_validation(client):  # noqa: F811
    catalog = client.get("/api/v1/bank/catalog").json()
    assert {card["card_id"] for card in catalog["cards"]} == {"card-asha", "card-ben", "card-chen"}
    assert "fictional" in catalog["disclaimer"]
    assert client.post("/api/v1/bank/payments", json=payment(card_id="card-nobody")).status_code == 404
    naive = payment(at=NOW.replace(tzinfo=None).isoformat())
    assert client.post("/api/v1/bank/payments", json=naive).status_code == 422
    assert client.post("/api/v1/bank/payments", json=payment(amount=-5)).status_code == 422
    too_long = payment(history=attempts(1) * 201)
    assert client.post("/api/v1/bank/payments", json=too_long).status_code == 422


@pytest.mark.parametrize("field", ["ground_truth_fraud", "features"])
def test_payment_rejects_extra_fields(client, field):  # noqa: F811
    assert client.post("/api/v1/bank/payments", json=payment(**{field: True})).status_code == 422
