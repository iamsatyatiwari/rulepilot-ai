"""Golden-set evaluation: expected investigation outcomes for prompt and model changes.

Each case names an advisory, a dataset, and the outcomes a correct run must
produce. Checks cover status, deterministic coverage, guardrails, quote
verification, held-out discipline, and whether the selected rule uses fields
that measure the advisory's behaviour. They never look at held-out metric
values, so prompts and models are not tuned against the test split.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.agent.orchestrator import InvestigationReport, InvestigationStatus
from app.agent.tools import CoverageStatus


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    advisory_id: StrictStr
    dataset_id: StrictStr
    expected_status: Annotated[list[InvestigationStatus], Field(min_length=1)]
    expected_coverage: Annotated[list[CoverageStatus], Field(min_length=1)]
    # When a rule is selected it must use at least one of these fields.
    relevant_fields: list[StrictStr] = []
    note: StrictStr = ""


GOLDEN_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        case_id="card-testing-payments-v3",
        advisory_id="jpm-card-testing",
        dataset_id="payments-scenario-v3",
        expected_status=["pending_human_review"],
        # The advisory also mentions signals we do not hold (e.g. IP address), so partial is correct too.
        expected_coverage=["testable", "partially_testable"],
        relevant_fields=["amount", "transactions_1h", "transactions_24h", "declined_attempts_24h", "card_present"],
        note="Card testing is testable and the baseline misses it.",
    ),
    GoldenCase(
        case_id="sim-swap-payments-v3",
        advisory_id="fbi-ic3-sim-swap-2022",
        dataset_id="payments-scenario-v3",
        expected_status=["pending_human_review"],
        expected_coverage=["testable", "partially_testable"],
        relevant_fields=["days_since_sim_change", "new_device", "credential_resets_24h", "new_payee"],
        note="SIM-change, device, credential-reset, and payee fields make the advisory testable.",
    ),
    GoldenCase(
        case_id="sim-swap-card-v2",
        advisory_id="fbi-ic3-sim-swap-2022",
        dataset_id="card-scenario-v2",
        expected_status=["not_testable"],
        expected_coverage=["not_testable"],
        note="Without SIM or device data the system must refuse rather than map onto unrelated fields.",
    ),
    GoldenCase(
        case_id="card-testing-card-v2",
        advisory_id="jpm-card-testing",
        dataset_id="card-scenario-v2",
        expected_status=["pending_human_review"],
        # The advisory also mentions signals we do not hold (e.g. IP address), so partial is correct too.
        expected_coverage=["testable", "partially_testable"],
        relevant_fields=["amount", "transactions_1h", "transactions_24h", "declined_attempts_24h", "card_present"],
        note="Matches the original v2 live run (14 Oct).",
    ),
)


def check_report(case: GoldenCase, report: InvestigationReport) -> list[str]:
    """Return the reasons a report fails a golden case; an empty list means it passes."""
    failures: list[str] = []
    if report.advisory.advisory_id != case.advisory_id:
        failures.append(f"advisory {report.advisory.advisory_id!r} is not {case.advisory_id!r}")
    if report.dataset.dataset_id != case.dataset_id:
        failures.append(f"dataset {report.dataset.dataset_id!r} is not {case.dataset_id!r}")
    if report.status not in case.expected_status:
        failures.append(f"status {report.status!r} not in {case.expected_status}")
    coverage = (report.coverage or {}).get("status")
    if coverage not in case.expected_coverage:
        failures.append(f"coverage {coverage!r} not in {case.expected_coverage}")
    failed_checks = [check.check for check in report.guardrails if not check.passed]
    if failed_checks:
        failures.append("guardrails failed: " + "; ".join(failed_checks))
    if not report.evidence_quotes or not all(quote.get("verified") for quote in report.evidence_quotes):
        failures.append("evidence quotes missing or not verified verbatim")
    if report.status == "pending_human_review":
        if report.selected_rule is None or report.holdout is None:
            failures.append("pending review without a selected rule and one held-out evaluation")
    elif report.holdout is not None:
        failures.append(f"held-out test used although status is {report.status!r}")
    if report.selected_rule is not None and case.relevant_fields:
        used = {condition.field for condition in report.selected_rule.conditions}
        if not used & set(case.relevant_fields):
            failures.append(f"selected rule uses {sorted(used)}, none of {case.relevant_fields}")
    return failures
