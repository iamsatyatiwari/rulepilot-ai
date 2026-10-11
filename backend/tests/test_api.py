from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def candidate_payload():
    return {
        "rule_id": "API-CANDIDATE-01",
        "name": "Large amount candidate",
        "description": "Flags a synthetic high-amount transaction.",
        "rationale": "Example request for the public API.",
        "conditions": [
            {"field": "amount", "operator": "greater_than", "value": 1500}
        ],
        "logical_operator": "and",
        "status": "draft",
        "version": 1,
    }


def test_existing_root_and_health_endpoints_remain_available():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_frontend_origin_can_send_api_post_requests():
    response = client.options(
        "/api/v1/rules/discover",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_rules_list_returns_baseline_only():
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["rule_id"] == "RP-BASELINE-001"


def test_evaluate_endpoint_returns_predictions_without_features():
    response = client.post(
        "/api/v1/rules/evaluate",
        json={"rule": candidate_payload(), "transaction_ids": ["SYN-0001", "SYN-0002"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rule_id"] == "API-CANDIDATE-01"
    assert len(body["predictions"]) == 2
    assert "amount" not in body["predictions"][0]
    assert body["metrics"]["total_evaluated"] == 2


def test_backtest_compares_baseline_and_candidate_on_test_split():
    response = client.post(
        "/api/v1/backtests/run",
        json={"candidate_rule": candidate_payload(), "seed": 41},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_split"] == "test"
    assert body["baseline_metrics"]["total_evaluated"] == body["candidate_metrics"]["total_evaluated"]
    assert isinstance(body["fraud_missed_by_baseline"], list)
    assert isinstance(body["fraud_missed_by_candidate"], list)
    assert len(body["fraud_missed_by_baseline"]) == body["baseline_metrics"]["false_negatives"]
    assert len(body["fraud_missed_by_candidate"]) == body["candidate_metrics"]["false_negatives"]


def test_discovery_endpoint_returns_candidate_and_evidence():
    response = client.post("/api/v1/rules/discover", json={"seed": 41})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "candidate_found"
    assert body["candidate_rule"]["conditions"]
    assert body["validation_metrics"]["total_evaluated"] == body["validation_count"]
    assert body["candidate_test_metrics"]["total_evaluated"] == body["test_count"]


def test_invalid_rules_and_duplicate_baseline_id_have_clear_statuses():
    invalid = candidate_payload()
    invalid["conditions"][0]["field"] = "ground_truth_fraud"
    assert client.post("/api/v1/rules/evaluate", json={"rule": invalid}).status_code == 422

    duplicate = candidate_payload()
    duplicate["rule_id"] = "RP-BASELINE-001"
    assert client.post("/api/v1/rules/evaluate", json={"rule": duplicate}).status_code == 409
