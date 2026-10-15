import functools

import pytest
from fastapi.testclient import TestClient

import app.investigations_api as investigations_api
from app.baseline import BASELINE_RULE
from app.data import DEMO_FEED_MAX, create_card_scenario_dataset, create_demo_feed, create_payments_scenario_dataset
from app.governance import GovernanceStore
from app.intel.advisories import load_curated_advisories
from app.main import app
from app.rules.models import Transaction
from app.scoring import score_transaction
from app.storage import LocalJsonBackend
from test_investigations import CARD_ID, card_testing_agent

CARD_TESTING_TXN = {
    "transaction_id": "T-CT",
    "amount": 4.5,
    "account_age_days": 300,
    "transactions_24h": 9,
    "distance_from_home_km": 12.0,
    "transactions_1h": 7,
    "declined_attempts_24h": 5,
    "card_present": 0,
}


@pytest.fixture
def store(tmp_path):
    return GovernanceStore(LocalJsonBackend(tmp_path))


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-real")
    monkeypatch.setattr(
        investigations_api,
        "run_investigation",
        functools.partial(investigations_api.run_investigation, agent_runner=card_testing_agent),
    )
    app.dependency_overrides[investigations_api.get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def approve_card_testing_rule(client):
    created = client.post("/api/v1/investigations", json={"advisory_id": CARD_ID}).json()
    investigation_id = created["report"]["investigation_id"]
    review = client.post(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "approve", "reviewer": "analyst", "comment": "Shadow test first."},
    )
    assert review.status_code == 200
    return created["report"]["selected_rule"]["rule_id"]


# ---- demo feed ---------------------------------------------------------------


def test_demo_feed_is_deterministic_bounded_and_not_dataset_records():
    first, again = create_demo_feed(30, seed=5), create_demo_feed(30, seed=5)
    assert first == again
    assert create_demo_feed(30, seed=6) != first
    assert all(t.transaction_id.startswith("FEED-5-") for t in first)
    dataset_features = {
        t.model_dump_json(exclude={"transaction_id"})
        for t in [*create_card_scenario_dataset(), *create_payments_scenario_dataset()]
    }
    assert not any(t.model_dump_json(exclude={"transaction_id"}) in dataset_features for t in first)
    for bad in (0, DEMO_FEED_MAX + 1):
        with pytest.raises(ValueError):
            create_demo_feed(bad, seed=1)


def test_demo_feed_over_represents_fraud_for_the_demo():
    feed = create_demo_feed(DEMO_FEED_MAX, seed=1)
    share = sum(bool(t.ground_truth_fraud) for t in feed) / len(feed)
    assert 0.15 < share < 0.6
    takeovers = [t for t in feed if t.ground_truth_fraud and t.credential_resets_24h and t.days_since_sim_change <= 10]
    assert takeovers, "the feed should include SIM-swap account-takeover fraud"


# ---- scoring -----------------------------------------------------------------


def test_shadow_rules_never_change_the_decision(store, client):
    rule_id = approve_card_testing_rule(client)
    transaction = Transaction.model_validate(CARD_TESTING_TXN)
    result = score_transaction(transaction, [BASELINE_RULE], store.catalog())
    assert result.decision == "allow"
    assert result.decided_by == []
    assert result.shadow_flagged_by == [rule_id]
    assert result.caught_only_in_shadow is True
    assert result.shadow_rules[0].investigation_id is not None


def test_active_rule_flags_and_missing_fields_fail_closed():
    big = Transaction(transaction_id="T-BIG", amount=2500.0)
    result = score_transaction(big, [BASELINE_RULE], [])
    assert result.decision == "flag" and result.decided_by == [BASELINE_RULE.rule_id]
    empty = score_transaction(Transaction(transaction_id="T-EMPTY"), [BASELINE_RULE], [])
    assert empty.decision == "allow"
    assert empty.active_rules[0].missing_fields == ["amount"]


def test_score_endpoint_ignores_supplied_label_and_rejects_bad_input(client):
    approve_card_testing_rule(client)
    labelled = dict(CARD_TESTING_TXN, ground_truth_fraud=False)
    body = client.post("/api/v1/transactions/score", json={"transaction": labelled}).json()
    # Approval activates the rule: it now decides, and the label supplied by the caller is ignored.
    assert body["decision"] == "flag" and body["caught_only_by_approved"] is True
    assert body["approved_flagged_by"] == body["decided_by"]
    for payload in (
        {"transaction": dict(CARD_TESTING_TXN, unknown_field=1)},
        {"transaction": dict(CARD_TESTING_TXN, amount="1e9")},
        {"transaction": CARD_TESTING_TXN, "extra": True},
    ):
        assert client.post("/api/v1/transactions/score", json=payload).status_code == 422


def test_simulate_summary_counts_fraud_caught_by_approved_rules(client):
    before = client.post("/api/v1/transactions/simulate", json={"count": 40, "seed": 3}).json()
    assert before["summary"]["approved_rules"] == 0
    assert before["summary"]["fraud_caught_by_approved_rules"] == 0

    approve_card_testing_rule(client)
    body = client.post("/api/v1/transactions/simulate", json={"count": 40, "seed": 3}).json()
    items, summary = body["items"], body["summary"]
    assert summary["transactions"] == len(items) == 40
    assert summary["synthetic_fraud"] == sum(item["synthetic_fraud"] for item in items)
    assert summary["approved_rules"] == 1 and summary["fraud_caught_by_approved_rules"] > 0
    assert summary["fraud_caught_only_in_shadow"] == 0
    assert summary["fraud_caught_by_active_rules"] + summary["fraud_missed_by_all_rules"] == summary["synthetic_fraud"]
    # Approval activated the rule: payments it catches are now flagged, others are unchanged.
    after = [i["score"]["decision"] for i in items]
    assert after != [i["score"]["decision"] for i in before["items"]]
    assert all(i["score"]["decision"] == "flag" for i in items if i["score"]["caught_only_by_approved"])
    assert all(item["score"]["transaction_id"] == item["transaction"]["transaction_id"] for item in items)
    assert "synthetic" in body["disclaimer"]


@pytest.mark.parametrize("payload", [{"count": 0}, {"count": DEMO_FEED_MAX + 1}, {"seed": -1}, {"mode": "x"}])
def test_simulate_rejects_out_of_bounds_requests(client, payload):
    assert client.post("/api/v1/transactions/simulate", json=payload).status_code == 422


# ---- scheduled ingestion -----------------------------------------------------

TOKEN_HEADER = {"X-RulePilot-Ingest-Token": "scheduler-secret"}


def test_ingestion_requires_configuration_and_a_valid_token(client, monkeypatch):
    monkeypatch.delenv("RULEPILOT_INGEST_TOKEN", raising=False)
    assert client.post("/api/v1/ingestion/run", headers=TOKEN_HEADER).status_code == 503
    monkeypatch.setenv("RULEPILOT_INGEST_TOKEN", "scheduler-secret")
    assert client.post("/api/v1/ingestion/run").status_code == 401
    assert client.post("/api/v1/ingestion/run", headers={"X-RulePilot-Ingest-Token": "wrong"}).status_code == 401
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(name, raising=False)
    assert client.post("/api/v1/ingestion/run", headers=TOKEN_HEADER).status_code == 503


def test_ingestion_processes_one_new_advisory_per_call_then_stops(client, store, monkeypatch):
    monkeypatch.setenv("RULEPILOT_INGEST_TOKEN", "scheduler-secret")
    curated = sorted(load_curated_advisories())
    seen: list[str] = []
    for _ in curated:
        body = client.post("/api/v1/ingestion/run", headers=TOKEN_HEADER).json()
        assert len(body["investigated"]) == 1
        assert body["investigated"][0]["origin"] == "scheduled"
        seen.append(body["investigated"][0]["advisory_id"])
    assert sorted(seen) == curated
    final = client.post("/api/v1/ingestion/run", headers=TOKEN_HEADER).json()
    assert final["investigated"] == [] and final["remaining"] == []
    assert sorted(final["already_investigated"]) == curated
    events = [e for e in store.audit() if e.event == "investigation_completed"]
    assert len(events) == len(curated) and all(e.detail["origin"] == "scheduled" for e in events)


def test_ingestion_skips_advisories_with_an_existing_live_run(client, monkeypatch):
    monkeypatch.setenv("RULEPILOT_INGEST_TOKEN", "scheduler-secret")
    client.post("/api/v1/investigations", json={"advisory_id": CARD_ID})
    body = client.post("/api/v1/ingestion/run", headers=TOKEN_HEADER).json()
    assert CARD_ID in body["already_investigated"]
    assert all(item["advisory_id"] != CARD_ID for item in body["investigated"])


def test_recorded_demo_runs_do_not_count_as_investigated(store):
    from app.agent.orchestrator import InvestigationReport
    import json

    for path in sorted(investigations_api.RECORDED_DIR.glob("*.json")):
        report = InvestigationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
        store.add_recorded(report.model_copy(update={"origin": "recorded"}))
    assert store.investigated_sources() == set()
