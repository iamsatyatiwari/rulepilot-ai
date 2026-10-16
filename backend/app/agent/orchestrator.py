"""Deterministic orchestration around one bounded agent run.

The agent proposes; this module decides what is reported. Coverage, quote
verification, guardrail checks, the single held-out evaluation, and the final
status are computed here by plain Python.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.agent.agent import AgentRunStats, run_adk_agent
from app.agent.schemas import AdvisoryFindings, AgentConclusion
from app.agent.tools import (
    InvestigationContext,
    InvestigationToolkit,
    coverage_for_fields,
    run_final_holdout,
)
from app.backtest import SplitComparison
from app.baseline import BASELINE_RULE
from app.config import Settings
from app.datasets import DatasetInfo, get_dataset
from app.evaluation import EvaluationMetrics
from app.intel.advisories import Advisory, AdvisorySummary, summarize, verify_quotes
from app.rules.models import Rule

InvestigationStatus = Literal[
    "pending_human_review",
    "covered_by_existing_rules",
    "insufficient_evidence",
    "not_testable",
    "agent_incomplete",
]
AgentRunner = Callable[[InvestigationToolkit, Advisory, Settings], Awaitable[AgentRunStats]]


class GuardrailCheck(BaseModel):
    check: str
    passed: bool
    detail: str


class TraceStep(BaseModel):
    step: int
    tool: str
    arguments: dict[str, Any]
    ok: bool
    summary: str


class CandidateEvidence(BaseModel):
    rule: Rule
    validation: SplitComparison


class ModelRun(BaseModel):
    provider: str = "google-gemini"
    framework: str = "google-adk"
    model: str
    model_version: str | None
    max_llm_calls: int
    timeout_seconds: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    errors: list[str]


class Delta(BaseModel):
    recall_change: float
    precision_change: float
    false_positive_rate_change: float
    alert_change: int
    fraud_newly_detected: int


class InvestigationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    created_at: datetime
    origin: Literal["live", "recorded", "scheduled"] = "live"
    status: InvestigationStatus
    headline: str
    advisory: AdvisorySummary
    dataset: DatasetInfo
    seed: int
    split_sizes: dict[str, int]
    model_run: ModelRun
    findings: AdvisoryFindings | None
    evidence_quotes: list[dict[str, Any]]
    coverage: dict[str, Any] | None
    agent_conclusion: AgentConclusion | None
    candidates: list[CandidateEvidence]
    selected_rule: Rule | None
    baseline_rule: Rule
    reference_rules: list[Rule] = []
    review_history_used: int = 0
    holdout: SplitComparison | None
    holdout_delta: Delta | None
    guardrails: list[GuardrailCheck]
    trace: list[TraceStep]
    limitations: list[str]
    # Set for investigations started from customer fraud reports: how many reported cases the proposed rule catches.
    customer_report_check: dict[str, int] | None = None


def _delta(baseline: EvaluationMetrics, combined: EvaluationMetrics) -> Delta:
    return Delta(
        recall_change=combined.recall - baseline.recall,
        precision_change=combined.precision - baseline.precision,
        false_positive_rate_change=combined.false_positive_rate - baseline.false_positive_rate,
        alert_change=combined.total_flagged - baseline.total_flagged,
        fraud_newly_detected=combined.true_positives - baseline.true_positives,
    )


def _summarize_result(tool: str, result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return f"Rejected: {result.get('error', 'invalid input')}"
    if tool == "get_rule_catalog":
        return f"{len(result['existing_rules'])} existing rule(s); {len(result['available_fields'])} available fields"
    if tool == "get_training_profile":
        return f"Training split profile: {result['records']} records, {result['fraud_records']} fraud"
    if tool == "check_field_coverage":
        missing = ", ".join(result["missing_fields"]) or "none"
        return f"Coverage {result['status']}; missing: {missing}"
    if tool == "evaluate_candidate_rule":
        candidate, combined, baseline = result["candidate"], result["baseline_or_candidate"], result["baseline"]
        return (
            f"{result['rule_id']} on validation: candidate recall {candidate['recall']:.0%}, "
            f"rule-set recall {baseline['recall']:.0%} -> {combined['recall']:.0%}, "
            f"FPR {baseline['false_positive_rate']:.2%} -> {combined['false_positive_rate']:.2%}"
        )
    if tool == "get_review_history":
        return f"{result['count']} prior human decision(s) returned as data"
    if tool == "submit_findings":
        return "Structured findings and conclusion recorded"
    return "ok"


ASSESSMENT_FOR_STATUS = {
    "not_testable": {"not_testable_with_available_data", "insufficient_evidence"},
    "partially_testable": {"gap_identified", "covered_by_existing_rules", "insufficient_evidence"},
    "testable": {"gap_identified", "covered_by_existing_rules", "insufficient_evidence"},
}


async def run_investigation(
    advisory: Advisory,
    dataset_id: str,
    seed: int,
    settings: Settings,
    agent_runner: AgentRunner = run_adk_agent,
    approved_rules: list[Rule] | None = None,
    review_history: list[dict[str, Any]] | None = None,
) -> InvestigationReport:
    """Run one agent investigation, then verify and evaluate its proposal deterministically.

    ``approved_rules`` (human-approved, inactive) join the baseline as the
    reference rule set; ``review_history`` is offered to the agent as data.
    """
    dataset, records = get_dataset(dataset_id)
    investigation_id = uuid.uuid4().hex
    reference_rules = [BASELINE_RULE, *(approved_rules or [])]
    context = InvestigationContext(
        run_id=investigation_id,
        dataset=dataset,
        records=records,
        seed=seed,
        reference_rules=reference_rules,
        review_history=list(review_history or []),
    )
    toolkit = InvestigationToolkit(context)
    stats = await agent_runner(toolkit, advisory, settings)

    findings, conclusion = context.findings, context.conclusion
    guardrails: list[GuardrailCheck] = [
        GuardrailCheck(check="Untrusted input isolated", passed=True, detail="Advisory text was delimited as data; the agent had no network, file, shell, or code tools."),
        GuardrailCheck(check="LLM call budget", passed=stats.llm_calls <= settings.agent_max_llm_calls, detail=f"{stats.llm_calls} of {settings.agent_max_llm_calls} model calls used."),
        GuardrailCheck(check="Candidate budget", passed=len(context.candidates) <= context.max_candidates, detail=f"{len(context.candidates)} of {context.max_candidates} candidates evaluated on validation."),
    ]

    coverage = None
    quotes: list[dict[str, Any]] = []
    holdout = None
    selected_rule = None
    if findings is None or conclusion is None:
        status: InvestigationStatus = "agent_incomplete"
        headline = "The agent did not submit findings; no recommendation was produced."
    else:
        coverage = coverage_for_fields(findings.required_fields, context.available_fields, reference_rules)
        quotes = verify_quotes(findings.evidence_quotes, advisory.excerpt)
        verified = sum(1 for quote in quotes if quote["verified"])
        guardrails.append(GuardrailCheck(check="Evidence quotes verified", passed=bool(quotes) and verified == len(quotes), detail=f"{verified} of {len(quotes)} quotes found verbatim in the source text."))
        consistent = conclusion.coverage_assessment in ASSESSMENT_FOR_STATUS[coverage["status"]]
        guardrails.append(GuardrailCheck(check="Agent coverage claim matches data", passed=consistent, detail=f"Deterministic coverage is '{coverage['status']}'; agent assessed '{conclusion.coverage_assessment}'."))

        selected_id = conclusion.selected_candidate_rule_id
        if coverage["status"] == "not_testable":
            status = "not_testable"
            headline = "The advisory's behaviors require data fields this dataset does not contain; no rule was tested."
            if selected_id:
                guardrails.append(GuardrailCheck(check="No candidate without testable data", passed=False, detail="The agent selected a candidate although required fields are unavailable; it was not evaluated on test."))
        elif selected_id is None and conclusion.coverage_assessment == "covered_by_existing_rules":
            status = "covered_by_existing_rules"
            names = ", ".join(rule.rule_id for rule in reference_rules)
            headline = f"The agent assessed this technique as already covered by the reviewed rule set ({names}); no new rule is proposed."
        elif selected_id is None:
            status = "insufficient_evidence"
            headline = "No candidate was supported by validation evidence; nothing is proposed for review."
        else:
            selected_rule = context.candidates[selected_id]
            holdout = run_final_holdout(context, selected_id)
            status = "pending_human_review"
            delta = _delta(holdout.baseline_metrics, holdout.combined_metrics)
            headline = (
                f"Adding {selected_id} to {len(reference_rules)} existing rule(s) changed held-out rule-set recall by {delta.recall_change * 100:+.1f} pp "
                f"and false-positive rate by {delta.false_positive_rate_change * 100:+.2f} pp "
                f"({delta.alert_change:+d} alerts). Awaiting human review."
            )
        guardrails.append(GuardrailCheck(check="Held-out test used at most once", passed=not holdout or context.holdout_used, detail="The model never accessed the test split; the orchestrator evaluated only the selected candidate." if holdout else "The test split was not used."))
        if selected_rule is not None:
            guardrails.append(GuardrailCheck(check="Candidate is a non-active draft", passed=selected_rule.status.value == "draft", detail="Schema-validated rule; approval and activation are separate human decisions."))

    trace = [
        TraceStep(step=index + 1, tool=call.tool, arguments=call.arguments, ok=bool(call.result.get("ok")), summary=_summarize_result(call.tool, call.result))
        for index, call in enumerate(context.tool_calls)
    ]
    limitations = [
        dataset.limitations,
        "Public intelligence describes techniques; it is not transaction ground truth.",
        f"Metrics come from a {context.split_sizes['test']}-record synthetic held-out split and are not real-world detection rates.",
    ]
    if conclusion:
        limitations.extend(item for item in conclusion.limitations if item not in limitations)

    return InvestigationReport(
        investigation_id=investigation_id,
        created_at=datetime.now(timezone.utc),
        status=status,
        headline=headline,
        advisory=summarize(advisory),
        dataset=dataset,
        seed=seed,
        split_sizes=context.split_sizes,
        model_run=ModelRun(
            model=stats.model_used or settings.gemini_model,
            model_version=stats.model_version,
            max_llm_calls=settings.agent_max_llm_calls,
            timeout_seconds=settings.agent_timeout_seconds,
            llm_calls=stats.llm_calls,
            input_tokens=stats.input_tokens,
            output_tokens=stats.output_tokens,
            errors=stats.errors,
        ),
        findings=findings,
        evidence_quotes=quotes,
        coverage=coverage,
        agent_conclusion=conclusion,
        candidates=[CandidateEvidence(rule=context.candidates[rule_id], validation=result) for rule_id, result in context.validation_results.items()],
        selected_rule=selected_rule,
        baseline_rule=BASELINE_RULE,
        reference_rules=reference_rules,
        review_history_used=len(context.review_history),
        holdout=holdout,
        holdout_delta=_delta(holdout.baseline_metrics, holdout.combined_metrics) if holdout else None,
        guardrails=guardrails,
        trace=trace,
        limitations=limitations[:8],
    )
