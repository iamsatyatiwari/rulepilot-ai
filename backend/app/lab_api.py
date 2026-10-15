"""HTTP endpoints for the rule lab: explain, generate examples, and manage labelled test cases."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.baseline import BASELINE_RULE
from app.governance import GovernanceStore
from app.investigations_api import get_store
from app.rule_lab import (
    CaseSource,
    Explanation,
    RunSummary,
    TestCase,
    TestCaseInput,
    TestCaseStore,
    case_store,
    explain,
    generate_example,
    run_cases,
)
from app.rules.models import Rule, Transaction

router = APIRouter(prefix="/api/v1/lab", tags=["rule lab"])
def get_cases(store: GovernanceStore = Depends(get_store)) -> TestCaseStore:
    return case_store(store.backend)


class LabRule(BaseModel):
    rule: Rule
    source: Literal["baseline", "approved_active", "candidate"]
    label: str


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: Rule
    transaction: Transaction


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: Rule
    match: bool


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: Rule
    source: CaseSource | None = None


@router.get("/rules", response_model=list[LabRule])
def rules(store: GovernanceStore = Depends(get_store)) -> list[LabRule]:
    """The baseline, every approved (active) rule, and every candidate any investigation proposed."""
    items = [LabRule(rule=BASELINE_RULE, source="baseline", label=f"{BASELINE_RULE.rule_id} · original rule (active)")]
    approved = {entry.rule.rule_id for entry in store.catalog()}
    for entry in store.catalog():
        items.append(LabRule(rule=entry.rule, source="approved_active", label=f"{entry.rule.rule_id} · {entry.technique or entry.rule.name} (approved, active)"))
    seen = set(approved)
    for summary in store.list():
        stored = store.get(summary.investigation_id)
        if stored is None:
            continue
        for candidate in stored.report.candidates:
            if candidate.rule.rule_id in seen:
                continue
            seen.add(candidate.rule.rule_id)
            items.append(LabRule(rule=candidate.rule, source="candidate", label=f"{candidate.rule.rule_id} · {candidate.rule.name} (candidate)"))
    return items


@router.post("/explain", response_model=Explanation)
def explain_rule(request: ExplainRequest) -> Explanation:
    return explain(request.rule, request.transaction.model_copy(update={"ground_truth_fraud": None}))


@router.post("/generate", response_model=Transaction)
def generate(request: GenerateRequest) -> Transaction:
    try:
        return generate_example(request.rule, request.match)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/cases", response_model=list[TestCase])
def list_cases(source: CaseSource | None = None, cases: TestCaseStore = Depends(get_cases)) -> list[TestCase]:
    return cases.list(source)


@router.post("/cases", response_model=TestCase, status_code=201)
def add_case(request: TestCaseInput, cases: TestCaseStore = Depends(get_cases)) -> TestCase:
    try:
        return cases.add(request, source="analyst")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: str, cases: TestCaseStore = Depends(get_cases)) -> None:
    try:
        deleted = cases.delete(case_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="unknown test case")


@router.post("/run", response_model=RunSummary)
def run(request: RunRequest, cases: TestCaseStore = Depends(get_cases)) -> RunSummary:
    """Run every stored case (optionally only analyst or customer-reported ones) against a rule."""
    return run_cases(request.rule, cases.list(request.source))
