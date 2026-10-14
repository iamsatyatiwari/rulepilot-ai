import asyncio
import json
from pathlib import Path

import pytest

from app.agent.orchestrator import InvestigationReport, run_investigation
from app.config import get_settings
from app.golden import GOLDEN_CASES, check_report
from app.intel.advisories import load_curated_advisories
from tests.test_investigations import card_testing_agent, overreaching_agent, sim_swap_agent

RECORDED = Path(__file__).resolve().parents[1] / "app" / "intel" / "recorded"
CASES = {case.case_id: case for case in GOLDEN_CASES}


def recorded(name):
    return InvestigationReport.model_validate(json.loads((RECORDED / name).read_text()))


def run(agent, case_id):
    case = CASES[case_id]
    advisory = load_curated_advisories()[case.advisory_id]
    return asyncio.run(run_investigation(advisory, case.dataset_id, 41, get_settings(), agent))


def test_golden_cases_reference_real_advisories_and_datasets():
    from app.datasets import DATASETS

    advisories = load_curated_advisories()
    assert len(CASES) == len(GOLDEN_CASES)
    for case in GOLDEN_CASES:
        assert case.advisory_id in advisories and case.dataset_id in DATASETS


@pytest.mark.parametrize(
    ("file", "case_id"),
    [
        ("card-testing-live-2026-10-15.json", "card-testing-payments-v3"),
        ("sim-swap-live-v3-2026-10-15.json", "sim-swap-payments-v3"),
        ("sim-swap-live-2026-10-14.json", "sim-swap-card-v2"),
    ],
)
def test_recorded_live_runs_pass_their_golden_case(file, case_id):
    assert check_report(CASES[case_id], recorded(file)) == []


@pytest.mark.parametrize(
    ("agent", "case_id"),
    [(card_testing_agent, "card-testing-payments-v3"), (sim_swap_agent, "sim-swap-payments-v3")],
)
def test_well_behaved_runs_pass_the_payments_cases(agent, case_id):
    assert check_report(CASES[case_id], run(agent, case_id)) == []


def test_checker_reports_wrong_status_and_overreach():
    failures = check_report(CASES["sim-swap-card-v2"], run(overreaching_agent, "sim-swap-card-v2"))
    assert any("guardrails failed" in failure for failure in failures)
    assert any("evidence quotes" in failure for failure in failures)
    report = run(card_testing_agent, "card-testing-payments-v3")
    failures = check_report(CASES["sim-swap-payments-v3"], report)
    assert any("advisory" in failure for failure in failures)
    assert any("selected rule uses" in failure for failure in failures)


def test_recorded_covered_run_compares_against_the_approved_rule():
    report = recorded("card-testing-covered-after-approval-2026-10-15.json")
    assert report.status == "covered_by_existing_rules"
    assert len(report.reference_rules) == 2 and report.review_history_used == 1
    assert report.holdout is None and all(check.passed for check in report.guardrails)


def test_checker_flags_a_held_out_run_without_review_status():
    report = run(card_testing_agent, "card-testing-payments-v3")
    tampered = report.model_copy(update={"status": "not_testable"})
    failures = check_report(CASES["card-testing-payments-v3"], tampered)
    assert any("held-out test used" in failure for failure in failures)
