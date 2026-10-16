"""Investigation storage, human review, the reviewed rule catalog, and audit.

Records are stored through a ``DocumentBackend`` (local JSON or Firestore) so
state survives restarts. Approval adds a rule to the reviewed catalog as
approved-but-inactive; a later reject or request-changes decision removes it.
Nothing here activates a rule.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.agent.orchestrator import InvestigationReport
from app.rules.models import Rule, RuleStatus
from app.storage import DocumentBackend

ReviewDecisionValue = Literal["approve", "reject", "request_changes"]
MAX_REVIEW_HISTORY = 10

INVESTIGATIONS = "investigations"
AUDIT = "audit"
CATALOG = "rule_catalog"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecisionValue
    reviewer: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    comment: Annotated[StrictStr, Field(min_length=1, max_length=1000)]


class ReviewRecord(ReviewRequest):
    review_id: str
    investigation_id: str
    rule_id: str
    rule_version: int
    decided_at: datetime
    # Approval activates the rule (team decision, 16 Oct); other decisions leave it inactive.
    activation: Literal["not_activated", "active"] = "not_activated"


class AuditEvent(BaseModel):
    event_id: str
    at: datetime
    investigation_id: str
    event: str
    detail: dict[str, Any]


class StoredInvestigation(BaseModel):
    report: InvestigationReport
    reviews: list[ReviewRecord] = []


class CatalogEntry(BaseModel):
    """A human-approved rule. Approval activates it; a later reject or request-changes removes it."""

    rule: Rule
    approved_by: str
    approved_at: datetime
    review_comment: str
    investigation_id: str
    advisory_title: str
    technique: str | None
    activation: Literal["not_activated", "active"] = "active"


class InvestigationSummary(BaseModel):
    investigation_id: str
    created_at: datetime
    origin: str
    status: str
    advisory_title: str
    advisory_id: str
    selected_rule_id: str | None
    review_decision: str | None


class GovernanceStore:
    def __init__(self, backend: DocumentBackend) -> None:
        self.backend = backend
        self._recorded: dict[str, StoredInvestigation] = {}
        self._lock = threading.Lock()

    # ---- storage helpers -------------------------------------------------

    def _save(self, item: StoredInvestigation) -> None:
        self.backend.put(INVESTIGATIONS, item.report.investigation_id, {
            "investigation_id": item.report.investigation_id,
            "created_at": item.report.created_at.isoformat(),
            "payload": item.model_dump_json(),
        })

    def _load(self, document: dict[str, Any]) -> StoredInvestigation | None:
        try:
            return StoredInvestigation.model_validate_json(document["payload"])
        except (KeyError, ValueError):
            return None

    def _append_audit(self, investigation_id: str, event: str, detail: dict[str, Any]) -> None:
        at = datetime.now(timezone.utc)
        event_id = f"{time.time_ns():020d}-{uuid.uuid4().hex[:6]}"
        record = AuditEvent(event_id=event_id, at=at, investigation_id=investigation_id, event=event, detail=detail)
        self.backend.put(AUDIT, event_id, {"payload": record.model_dump_json()})

    # ---- investigations --------------------------------------------------

    def add_recorded(self, report: InvestigationReport) -> None:
        """Register a recorded demo run in memory (not persisted until reviewed)."""
        self._recorded[report.investigation_id] = StoredInvestigation(report=report)

    def add(self, report: InvestigationReport) -> None:
        with self._lock:
            self._save(StoredInvestigation(report=report))
            self._append_audit(report.investigation_id, "investigation_completed", {
                "advisory_id": report.advisory.advisory_id,
                "advisory_sha256": report.advisory.content_sha256,
                "dataset_id": report.dataset.dataset_id,
                "dataset_version": report.dataset.version,
                "seed": report.seed,
                "origin": report.origin,
                "model": report.model_run.model,
                "status": report.status,
                "tool_calls": len(report.trace),
                "reference_rules": [rule.rule_id for rule in report.reference_rules],
                "selected_rule_id": report.selected_rule.rule_id if report.selected_rule else None,
            })

    def get(self, investigation_id: str) -> StoredInvestigation | None:
        try:
            document = self.backend.get(INVESTIGATIONS, investigation_id)
        except ValueError:
            return None
        stored = self._load(document) if document else None
        return stored or self._recorded.get(investigation_id)

    def _all(self) -> list[StoredInvestigation]:
        items = {item.report.investigation_id: item for item in self._recorded.values()}
        for document in self.backend.all(INVESTIGATIONS):
            item = self._load(document)
            if item is not None:
                items[item.report.investigation_id] = item
        return sorted(items.values(), key=lambda item: item.report.created_at, reverse=True)

    def investigated_sources(self) -> set[tuple[str, str]]:
        """(advisory_id, content SHA-256) pairs with a stored live or scheduled run; recorded demos excluded."""
        return {
            (item.report.advisory.advisory_id, item.report.advisory.content_sha256)
            for item in self._all()
            if item.report.origin != "recorded"
        }

    def list(self) -> list[InvestigationSummary]:
        return [
            InvestigationSummary(
                investigation_id=item.report.investigation_id,
                created_at=item.report.created_at,
                origin=item.report.origin,
                status=item.report.status,
                advisory_title=item.report.advisory.title,
                advisory_id=item.report.advisory.advisory_id,
                selected_rule_id=item.report.selected_rule.rule_id if item.report.selected_rule else None,
                review_decision=item.reviews[-1].decision if item.reviews else None,
            )
            for item in self._all()
        ]

    # ---- review and catalog ----------------------------------------------

    def review(self, investigation_id: str, request: ReviewRequest) -> ReviewRecord:
        with self._lock:
            item = self.get(investigation_id)
            if item is None:
                raise KeyError(investigation_id)
            rule = item.report.selected_rule
            if rule is None or item.report.status != "pending_human_review":
                raise ValueError("this investigation has no candidate awaiting review")
            record = ReviewRecord(
                **request.model_dump(),
                review_id=f"{investigation_id[:8]}-R{len(item.reviews) + 1}",
                investigation_id=investigation_id,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                decided_at=datetime.now(timezone.utc),
                activation="active" if request.decision == "approve" else "not_activated",
            )
            item.reviews.append(record)
            self._save(item)
            self._recorded.pop(investigation_id, None)
            self._append_audit(investigation_id, "review_recorded", {
                "decision": record.decision,
                "reviewer": record.reviewer,
                "rule_id": record.rule_id,
                "rule_version": record.rule_version,
                "activation": record.activation,
            })
            if record.decision == "approve":
                entry = CatalogEntry(
                    rule=rule.model_copy(update={"status": RuleStatus.APPROVED}),
                    approved_by=record.reviewer,
                    approved_at=record.decided_at,
                    review_comment=record.comment,
                    investigation_id=investigation_id,
                    advisory_title=item.report.advisory.title,
                    technique=item.report.findings.technique_name if item.report.findings else None,
                )
                self.backend.put(CATALOG, rule.rule_id, {"payload": entry.model_dump_json()})
                self._append_audit(investigation_id, "rule_added_to_catalog", {"rule_id": rule.rule_id, "activation": "active"})
            elif self.backend.get(CATALOG, rule.rule_id) is not None:
                self.backend.delete(CATALOG, rule.rule_id)
                self._append_audit(investigation_id, "rule_removed_from_catalog", {"rule_id": rule.rule_id, "decision": record.decision, "activation": "deactivated"})
            return record

    def catalog(self) -> list[CatalogEntry]:
        entries = []
        for document in self.backend.all(CATALOG):
            try:
                # Every catalog entry is active; entries stored before 16 Oct say "not_activated".
                entries.append(CatalogEntry.model_validate_json(document["payload"]).model_copy(update={"activation": "active"}))
            except (KeyError, ValueError):
                continue
        return sorted(entries, key=lambda entry: entry.approved_at)

    def approved_rules(self) -> list[Rule]:
        return [entry.rule for entry in self.catalog()]

    def review_history(self, limit: int = MAX_REVIEW_HISTORY) -> list[dict[str, Any]]:
        """Recent human decisions, summarized for the agent as untrusted data."""
        rows: list[tuple[datetime, dict[str, Any]]] = []
        for item in self._all():
            report = item.report
            rule = report.selected_rule
            for review in item.reviews:
                rows.append((review.decided_at, {
                    "decided_at": review.decided_at.isoformat(),
                    "decision": review.decision,
                    "reviewer_comment": review.comment[:300],
                    "advisory_title": report.advisory.title,
                    "technique": report.findings.technique_name if report.findings else None,
                    "rule_id": review.rule_id,
                    "conditions": [c.model_dump(mode="json") for c in rule.conditions] if rule else [],
                    "logical_operator": rule.logical_operator.value if rule else None,
                    "held_out_recall_change": round(report.holdout_delta.recall_change, 4) if report.holdout_delta else None,
                    "held_out_false_positive_rate_change": round(report.holdout_delta.false_positive_rate_change, 5) if report.holdout_delta else None,
                }))
        rows.sort(key=lambda row: row[0], reverse=True)
        return [row for _, row in rows[:limit]]

    # ---- audit -----------------------------------------------------------

    def audit(self, investigation_id: str | None = None) -> list[AuditEvent]:
        events = []
        for document in self.backend.all(AUDIT):
            try:
                event = AuditEvent.model_validate_json(document["payload"])
            except (KeyError, ValueError):
                continue
            if investigation_id is None or event.investigation_id == investigation_id:
                events.append(event)
        return sorted(events, key=lambda event: event.event_id)
