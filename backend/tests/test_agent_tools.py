import json

import pytest
from fastapi.testclient import TestClient

from app.agent.tools import (
    InvestigationContext,
    InvestigationToolkit,
    run_final_holdout,
)
from app.datasets import SCENARIO_DATASET_ID, get_dataset
from app.main import app

CARD_TEST_CONDITIONS = [
    {"field": "amount", "operator": "less_than", "value": 25},
    {"field": "transactions_1h", "operator": "greater_than_or_equal", "value": 3},
    {"field": "card_present", "operator": "equals", "value": 0},
]


def make_context(**overrides):
    info, records = get_dataset(SCENARIO_DATASET_ID)
    return InvestigationContext(run_id="run12345abc", dataset=info, records=records, seed=41, **overrides)


def evaluate(toolkit, conditions=CARD_TEST_CONDITIONS, name="Card testing burst"):
    return toolkit.evaluate_candidate_rule(
        name=name, rationale="Small CNP bursts.", conditions=conditions, logical_operator="and"
    )


def test_every_tool_result_is_json_serializable():
    toolkit = InvestigationToolkit(make_context())
    results = [
        toolkit.get_rule_catalog(),
        toolkit.get_training_profile(),
        toolkit.check_field_coverage(["amount", "device_fingerprint"]),
        evaluate(toolkit),
    ]
    for result in results:
        json.dumps(result)
        assert result["ok"] is True
    assert [call.tool for call in toolkit.context.tool_calls] == [
        "get_rule_catalog",
        "get_training_profile",
        "check_field_coverage",
        "evaluate_candidate_rule",
    ]


def test_catalog_lists_only_populated_fields():
    v1_info, v1_records = get_dataset("synthetic-v1")
    v1 = InvestigationToolkit(InvestigationContext("r1", v1_info, v1_records, 41)).get_rule_catalog()
    v2 = InvestigationToolkit(make_context()).get_rule_catalog()
    assert "transactions_1h" not in v1["available_fields"]
    assert "transactions_1h" in v2["available_fields"]
    assert v2["existing_rules"][0]["rule_id"] == "RP-BASELINE-001"


def test_training_profile_ignores_validation_and_test_records():
    info, records = get_dataset(SCENARIO_DATASET_ID)
    context = InvestigationContext("run-copy", info, [row.model_copy() for row in records], 41)
    first = InvestigationToolkit(context).get_training_profile()
    for row in [*context._validation, *context._test]:
        object.__setattr__(row, "amount", 999999.0)
    second = InvestigationToolkit(context).get_training_profile()
    assert first["fields"] == second["fields"]
    assert first["records"] == len(context._train)


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        (["amount", "transactions_1h"], "testable"),
        (["amount", "sim_swap_event"], "partially_testable"),
        (["sim_swap_event", "device_change"], "not_testable"),
    ],
)
def test_field_coverage_is_deterministic(fields, status):
    result = InvestigationToolkit(make_context()).check_field_coverage(fields)
    assert result["status"] == status
    assert result["existing_rule_fields"] == ["amount"]


@pytest.mark.parametrize("bad", [[], ["x" * 65], ["a"] * 21, "amount"])
def test_field_coverage_rejects_unbounded_input(bad):
    assert InvestigationToolkit(make_context()).check_field_coverage(bad)["ok"] is False


def test_candidate_is_evaluated_on_validation_only_and_forced_to_draft():
    context = make_context()
    test_ids = {row.transaction_id for row in context._test}
    result = evaluate(InvestigationToolkit(context))
    assert result["ok"] and result["split"] == "validation"
    assert result["candidate"]["evaluated"] == len(context._validation)
    rule = context.candidates[result["rule_id"]]
    assert rule.status.value == "draft" and rule.created_by == "rulepilot-agent"
    comparison = context.validation_results[result["rule_id"]]
    assert not test_ids & set(comparison.fraud_missed_by_candidate)


@pytest.mark.parametrize(
    "conditions",
    [
        [],
        [{"field": "ground_truth_fraud", "operator": "equals", "value": 1}],
        [{"field": "sim_swap_event", "operator": "equals", "value": 1}],
        [{"field": "amount", "operator": "exec", "value": 1}],
        [{"field": "amount", "operator": "less_than", "value": float("inf")}],
        CARD_TEST_CONDITIONS + [{"field": "declined_attempts_24h", "operator": "greater_than", "value": 1}],
    ],
)
def test_invalid_candidates_return_structured_errors(conditions):
    context = make_context()
    result = evaluate(InvestigationToolkit(context), conditions=conditions)
    assert result["ok"] is False and result["error"]
    assert context.candidates == {}


def test_candidate_budget_is_enforced():
    context = make_context(max_candidates=3)
    toolkit = InvestigationToolkit(context)
    for threshold in (10, 20, 30):
        assert evaluate(toolkit, [{"field": "amount", "operator": "less_than", "value": threshold}])["ok"]
    fourth = evaluate(toolkit, [{"field": "amount", "operator": "less_than", "value": 40}])
    assert fourth["ok"] is False and "budget" in fourth["error"]


def test_submit_findings_validates_selected_candidate_and_runs_once():
    context = make_context()
    toolkit = InvestigationToolkit(context)
    findings = {
        "technique_name": "Card testing",
        "summary": "Small authorizations to validate stolen cards.",
        "behaviors": ["many small CNP attempts"],
        "indicators": ["repeated declines"],
        "required_fields": ["amount", "transactions_1h"],
        "testable_hypotheses": ["small high-velocity CNP bursts"],
        "uncertainties": ["synthetic data"],
        "evidence_quotes": ["card testing"],
    }
    conclusion = {
        "coverage_assessment": "gap_identified",
        "selected_candidate_rule_id": "AGT-missing-1",
        "recommendation": "recommend_for_review",
        "rationale": "Baseline only checks amount.",
        "limitations": ["synthetic"],
    }
    assert toolkit.submit_findings(findings, conclusion)["ok"] is False
    rule_id = evaluate(toolkit)["rule_id"]
    conclusion["selected_candidate_rule_id"] = rule_id
    assert toolkit.submit_findings(findings, conclusion)["ok"] is True
    assert toolkit.submit_findings(findings, conclusion)["ok"] is False
    assert context.conclusion.selected_candidate_rule_id == rule_id


def test_holdout_runs_once_and_matches_backtest_endpoint():
    context = make_context()
    rule_id = evaluate(InvestigationToolkit(context))["rule_id"]
    holdout = run_final_holdout(context, rule_id)
    with pytest.raises(RuntimeError):
        run_final_holdout(context, rule_id)

    rule = context.candidates[rule_id].model_dump(mode="json")
    response = TestClient(app).post(
        "/api/v1/backtests/run",
        json={"candidate_rule": rule, "seed": 41, "dataset_id": SCENARIO_DATASET_ID},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_metrics"] == holdout.candidate_metrics.model_dump()
    assert body["combined_metrics"] == holdout.combined_metrics.model_dump()
    assert holdout.evaluated_split == "test"
