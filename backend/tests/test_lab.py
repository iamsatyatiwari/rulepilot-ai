import functools
from datetime import datetime, timedelta, timezone

import pytest

import app.investigations_api as investigations_api
from app.agent.agent import AgentRunStats
from app.rule_lab import explain, generate_example
from app.rules.models import Rule, Transaction
from test_investigations import conclusion, findings
from test_transactions import approve_card_testing_rule, client, store  # noqa: F401 (fixtures)

NOW = datetime(2026, 10, 16, 1, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def rule(conditions, logical="and"):
    return Rule.model_validate({
        "rule_id": "LAB-T1", "name": "t", "description": "d", "rationale": "r",
        "logical_operator": logical, "conditions": conditions,
    })


CARD_TESTING = rule([
    {"field": "transactions_1h", "operator": "greater_than_or_equal", "value": 5},
    {"field": "amount", "operator": "less_than", "value": 5},
])
SIM_SWAP = rule([
    {"field": "days_since_sim_change", "operator": "less_than_or_equal", "value": 2},
    {"field": "credential_resets_24h", "operator": "greater_than_or_equal", "value": 1},
])


def test_explain_shows_each_condition_and_fails_closed_on_missing_fields():
    result = explain(CARD_TESTING, Transaction(amount=3.0, transactions_1h=2))
    assert result.flagged is False
    assert [(c.field, c.value, c.passed) for c in result.conditions] == [("transactions_1h", 2.0, False), ("amount", 3.0, True)]
    missing = explain(CARD_TESTING, Transaction(amount=3.0))
    assert missing.conditions[0].passed is None and missing.flagged is False


@pytest.mark.parametrize("candidate", [CARD_TESTING, SIM_SWAP, rule([
    {"field": "new_device", "operator": "not_equals", "value": 0},
    {"field": "hour_of_day", "operator": "greater_than", "value": 21},
], "or")])
def test_generated_examples_match_or_miss_and_respect_field_ranges(candidate):
    hit, miss = generate_example(candidate, True), generate_example(candidate, False)
    assert explain(candidate, hit).flagged is True and explain(candidate, miss).flagged is False
    for example in (hit, miss):
        assert 0 <= example.hour_of_day <= 23 and example.new_device in (0, 1)


def test_impossible_rules_are_rejected(client):  # noqa: F811
    impossible = rule([
        {"field": "amount", "operator": "greater_than", "value": 100},
        {"field": "amount", "operator": "less_than", "value": 50},
    ]).model_dump(mode="json")
    assert client.post("/api/v1/lab/generate", json={"rule": impossible, "match": True}).status_code == 422


def test_cases_are_saved_run_against_a_rule_and_deleted(client):  # noqa: F811
    body = CARD_TESTING.model_dump(mode="json")
    hit = client.post("/api/v1/lab/generate", json={"rule": body, "match": True}).json()
    miss = client.post("/api/v1/lab/generate", json={"rule": body, "match": False}).json()
    first = client.post("/api/v1/lab/cases", json={"name": "burst", "transaction": hit, "expected": "fraud"})
    assert first.status_code == 201 and first.json()["source"] == "analyst"
    client.post("/api/v1/lab/cases", json={"name": "near miss", "transaction": miss, "expected": "legit"})
    client.post("/api/v1/lab/cases", json={"name": "missed fraud", "transaction": miss, "expected": "fraud"})
    run = client.post("/api/v1/lab/run", json={"rule": body}).json()
    assert (run["cases"], run["passed"], run["fraud_caught"], run["false_alarms"]) == (3, 2, 1, 0)
    assert client.delete(f"/api/v1/lab/cases/{first.json()['case_id']}").status_code == 204
    assert len(client.get("/api/v1/lab/cases").json()) == 2
    assert client.delete("/api/v1/lab/cases/case-unknown").status_code == 404
    bad = {"name": "x", "transaction": hit, "expected": "fraud", "source": "customer_report"}
    assert client.post("/api/v1/lab/cases", json=bad).status_code == 422


def test_lab_rules_list_baseline_approved_and_candidates(client):  # noqa: F811
    rule_id = approve_card_testing_rule(client)
    client.post("/api/v1/investigations", json={"advisory_id": "jpm-card-testing"})  # a second, unreviewed run
    sources = {item["rule"]["rule_id"]: item["source"] for item in client.get("/api/v1/lab/rules").json()}
    assert sources["RP-BASELINE-001"] == "baseline" and sources[rule_id] == "approved_active"
    assert "candidate" in sources.values()


def takeover_payment(minutes_ago=0):
    at = NOW - timedelta(minutes=minutes_ago)
    events = [{"at": (at - timedelta(hours=1)).isoformat(), "type": "sim_change"},
              {"at": (at - timedelta(minutes=30)).isoformat(), "type": "credential_reset"}]
    return {"card_id": "card-chen", "merchant_id": "m-transfer", "amount": 900.0, "at": at.isoformat(),
            "new_device": True, "security_events": events}


def report(client, minutes_ago=0):  # noqa: F811
    return client.post("/api/v1/bank/reports", json={"payment": takeover_payment(minutes_ago), "note": "not me"})


async def digest_agent(toolkit, advisory, settings):
    toolkit.get_rule_catalog()
    toolkit.check_field_coverage(["days_since_sim_change", "credential_resets_24h"])
    result = toolkit.evaluate_candidate_rule(
        name="Recent SIM change and credential reset", rationale="Reported frauds share both.",
        conditions=[{"field": "days_since_sim_change", "operator": "less_than_or_equal", "value": 3},
                    {"field": "credential_resets_24h", "operator": "greater_than_or_equal", "value": 1}],
        logical_operator="and",
    )
    quote = advisory.excerpt.split(". ")[0]
    toolkit.submit_findings(findings(["days_since_sim_change", "credential_resets_24h"], quotes=(quote,)),
                            conclusion("gap_identified", result["rule_id"]))
    return AgentRunStats(llm_calls=4, model_version="fake-model")


def test_customer_reports_are_stored_with_server_derived_features(client):  # noqa: F811
    created = report(client)
    assert created.status_code == 201
    case = created.json()
    assert case["source"] == "customer_report" and case["expected"] == "fraud"
    assert case["transaction"]["days_since_sim_change"] == 0 and case["transaction"]["credential_resets_24h"] == 1
    assert "Chen Wei" in case["created_by"]
    tampered = {"payment": takeover_payment(), "features": {"amount": 1}}
    assert client.post("/api/v1/bank/reports", json=tampered).status_code == 422


def test_missed_reports_trigger_one_investigation_with_a_reported_case_check(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(investigations_api, "run_investigation",
                        functools.partial(investigations_api.run_investigation, agent_runner=digest_agent))
    report(client, 10)
    report(client, 5)
    summary = client.get("/api/v1/customer-reports/summary").json()
    assert summary["missed_by_active_rules"] == 2 and summary["ready_to_investigate"] is False
    assert client.post("/api/v1/customer-reports/investigate").status_code == 409
    report(client, 1)
    summary = client.get("/api/v1/customer-reports/summary").json()
    assert summary["ready_to_investigate"] is True
    assert "3 of 3 reported payments happened within 3 days of a SIM change" in summary["digest_preview"]
    assert "Chen" not in summary["digest_preview"]

    stored = client.post("/api/v1/customer-reports/investigate").json()
    result = stored["report"]
    assert result["advisory"]["source_type"] == "customer_reports"
    assert result["status"] == "pending_human_review"
    assert result["customer_report_check"] == {"reported_cases": 3, "caught_by_proposed_rule": 3}
    assert all(check["passed"] for check in result["guardrails"])
    # The same set of reports is not investigated twice.
    assert client.get("/api/v1/customer-reports/summary").json()["ready_to_investigate"] is False

    # Approving the proposed rule makes the active rules catch the reports.
    client.post(f"/api/v1/investigations/{result['investigation_id']}/review",
                json={"decision": "approve", "reviewer": "analyst", "comment": "Covers reported takeovers."})
    assert client.get("/api/v1/customer-reports/summary").json()["missed_by_active_rules"] == 0
