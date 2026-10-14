"""HTTP endpoints for intelligence investigations, human review, and audit."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr, model_validator

from app.agent.orchestrator import InvestigationReport, run_investigation
from app.config import Settings, get_settings
from app.data import DEFAULT_SPLIT_SEED
from app.datasets import SCENARIO_DATASET_ID
from app.governance import (
    AuditEvent,
    CatalogEntry,
    GovernanceStore,
    InvestigationSummary,
    ReviewRecord,
    ReviewRequest,
    StoredInvestigation,
)
from app.baseline import BASELINE_RULE
from app.intel.advisories import Advisory, AdvisorySummary, load_curated_advisories, summarize
from app.rules.models import Rule
from app.storage import create_backend

MAX_CUSTOM_ADVISORY_CHARS = 8_000
MAX_CONCURRENT_INVESTIGATIONS = 2
MAX_INGEST_PER_RUN = 1
RECORDED_DIR = Path(__file__).parent / "intel" / "recorded"

router = APIRouter(prefix="/api/v1")
_run_slots = asyncio.Semaphore(MAX_CONCURRENT_INVESTIGATIONS)


@lru_cache(maxsize=1)
def _default_store() -> GovernanceStore:
    settings = get_settings()
    store = GovernanceStore(create_backend(settings.store, settings.data_dir, settings.gcp_project))
    for path in sorted(RECORDED_DIR.glob("*.json")):
        report = InvestigationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
        store.add_recorded(report.model_copy(update={"origin": "recorded"}))
    return store


def get_store() -> GovernanceStore:
    return _default_store()


class CustomAdvisoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    publisher: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    source_url: HttpUrl
    text: Annotated[StrictStr, Field(min_length=50, max_length=MAX_CUSTOM_ADVISORY_CHARS)]


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    advisory_id: StrictStr | None = None
    custom_advisory: CustomAdvisoryInput | None = None
    dataset_id: Literal["synthetic-v1", "card-scenario-v2"] = SCENARIO_DATASET_ID
    seed: Annotated[int, Field(ge=0, le=2**32 - 1)] = DEFAULT_SPLIT_SEED

    @model_validator(mode="after")
    def exactly_one_source(self) -> InvestigationRequest:
        if (self.advisory_id is None) == (self.custom_advisory is None):
            raise ValueError("provide exactly one of advisory_id or custom_advisory")
        return self


class AdvisoryListResponse(BaseModel):
    count: int
    items: list[AdvisorySummary]


class AgentStatus(BaseModel):
    configured: bool
    model: str
    framework: str = "google-adk"
    max_llm_calls: int
    timeout_seconds: int
    max_candidates: int = 3


def _resolve_advisory(request: InvestigationRequest) -> Advisory:
    if request.advisory_id is not None:
        advisory = load_curated_advisories().get(request.advisory_id)
        if advisory is None:
            raise HTTPException(status_code=404, detail="unknown advisory_id")
        return advisory
    custom = request.custom_advisory
    assert custom is not None
    digest = hashlib.sha256(custom.text.encode("utf-8")).hexdigest()[:12]
    return Advisory(
        advisory_id=f"custom-{digest}",
        title=custom.title,
        publisher=custom.publisher,
        source_url=custom.source_url,
        published_date=None,
        retrieved_at=date.today().isoformat(),
        source_type="analyst_supplied",
        rights_note="Supplied by an analyst; treated as untrusted input.",
        excerpt=custom.text,
    )


@router.get("/advisories", response_model=AdvisoryListResponse, tags=["intelligence"])
def list_advisories() -> AdvisoryListResponse:
    """List curated intelligence documents with source metadata and content hashes."""
    items = [summarize(advisory) for advisory in load_curated_advisories().values()]
    return AdvisoryListResponse(count=len(items), items=items)


@router.get("/agent/status", response_model=AgentStatus, tags=["intelligence"])
def agent_status(settings: Settings = Depends(get_settings)) -> AgentStatus:
    """Report whether the Gemini agent is configured; never returns credentials."""
    return AgentStatus(
        configured=settings.gemini_configured,
        model=settings.gemini_model,
        max_llm_calls=settings.agent_max_llm_calls,
        timeout_seconds=settings.agent_timeout_seconds,
    )


@router.post("/investigations", response_model=StoredInvestigation, tags=["intelligence"])
async def create_investigation(
    request: InvestigationRequest,
    settings: Settings = Depends(get_settings),
    store: GovernanceStore = Depends(get_store),
) -> StoredInvestigation:
    """Run the bounded agent on one advisory, then verify and backtest deterministically."""
    advisory = _resolve_advisory(request)
    if not settings.gemini_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured on the server")
    if _run_slots.locked():
        raise HTTPException(status_code=429, detail="investigation capacity is busy; retry shortly")
    async with _run_slots:
        report = await run_investigation(
            advisory,
            request.dataset_id,
            request.seed,
            settings,
            approved_rules=store.approved_rules(),
            review_history=store.review_history(),
        )
    store.add(report)
    stored = store.get(report.investigation_id)
    assert stored is not None
    return stored


@router.get("/investigations", response_model=list[InvestigationSummary], tags=["intelligence"])
def list_investigations(store: GovernanceStore = Depends(get_store)) -> list[InvestigationSummary]:
    return store.list()


@router.get("/investigations/{investigation_id}", response_model=StoredInvestigation, tags=["intelligence"])
def get_investigation(investigation_id: str, store: GovernanceStore = Depends(get_store)) -> StoredInvestigation:
    item = store.get(investigation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return item


@router.post("/investigations/{investigation_id}/review", response_model=ReviewRecord, tags=["governance"])
def review_investigation(
    investigation_id: str, request: ReviewRequest, store: GovernanceStore = Depends(get_store)
) -> ReviewRecord:
    """Record a human decision. Approval never activates the rule."""
    try:
        return store.review(investigation_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="investigation not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


class RuleCatalogResponse(BaseModel):
    active: list[Rule]
    approved_not_active: list[CatalogEntry]


@router.get("/rule-catalog", response_model=RuleCatalogResponse, tags=["governance"])
def rule_catalog(store: GovernanceStore = Depends(get_store)) -> RuleCatalogResponse:
    """The reviewed rule set: the active baseline plus human-approved, inactive rules."""
    return RuleCatalogResponse(active=[BASELINE_RULE], approved_not_active=store.catalog())


@router.get("/audit", response_model=list[AuditEvent], tags=["governance"])
def audit_log(investigation_id: str | None = None, store: GovernanceStore = Depends(get_store)) -> list[AuditEvent]:
    return store.audit(investigation_id)


class IngestionResult(BaseModel):
    investigated: list[InvestigationSummary]
    already_investigated: list[str]
    remaining: list[str]


@router.post("/ingestion/run", response_model=IngestionResult, tags=["intelligence"])
async def run_ingestion(
    settings: Settings = Depends(get_settings),
    store: GovernanceStore = Depends(get_store),
    x_rulepilot_ingest_token: Annotated[str | None, Header()] = None,
) -> IngestionResult:
    """Scheduled sweep (Cloud Scheduler): investigate curated advisories with no live run yet.

    An advisory counts as investigated when a live or scheduled run exists for
    the same content SHA-256, so an edited advisory is investigated again. At
    most one advisory is processed per call to keep each request bounded.
    """
    expected = settings.ingest_token
    if expected is None:
        raise HTTPException(status_code=503, detail="scheduled ingestion is not configured on the server")
    if not hmac.compare_digest((x_rulepilot_ingest_token or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid ingestion token")
    if not settings.gemini_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured on the server")

    done = store.investigated_sources()
    advisories = list(load_curated_advisories().values())
    already = [a.advisory_id for a in advisories if (a.advisory_id, a.content_sha256) in done]
    pending = [a for a in advisories if a.advisory_id not in already]
    investigated: list[InvestigationSummary] = []
    for advisory in pending[:MAX_INGEST_PER_RUN]:
        if _run_slots.locked():
            break
        async with _run_slots:
            report = await run_investigation(
                advisory,
                SCENARIO_DATASET_ID,
                DEFAULT_SPLIT_SEED,
                settings,
                approved_rules=store.approved_rules(),
                review_history=store.review_history(),
            )
        store.add(report.model_copy(update={"origin": "scheduled"}))
        investigated.extend(s for s in store.list() if s.investigation_id == report.investigation_id)
    processed = {s.advisory_id for s in investigated}
    return IngestionResult(
        investigated=investigated,
        already_investigated=already,
        remaining=[a.advisory_id for a in pending if a.advisory_id not in processed],
    )
