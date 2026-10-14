"""Investigation storage, human review decisions, and an append-only audit log.

Storage is a local JSON file per investigation plus a JSONL audit log. It is a
prototype store: on Cloud Run the filesystem is ephemeral, so records survive
only for the life of an instance. Approval never activates a rule.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.agent.orchestrator import InvestigationReport

ReviewDecisionValue = Literal["approve", "reject", "request_changes"]


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
    activation: Literal["not_activated"] = "not_activated"


class AuditEvent(BaseModel):
    event_id: int
    at: datetime
    investigation_id: str
    event: str
    detail: dict[str, Any]


class StoredInvestigation(BaseModel):
    report: InvestigationReport
    reviews: list[ReviewRecord] = []


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
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._items: dict[str, StoredInvestigation] = {}
        self._audit: list[AuditEvent] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        investigations = self.data_dir / "investigations"
        if investigations.is_dir():
            for path in sorted(investigations.glob("*.json")):
                try:
                    item = StoredInvestigation.model_validate_json(path.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                self._items[item.report.investigation_id] = item
        audit = self.data_dir / "audit.jsonl"
        if audit.is_file():
            for line in audit.read_text(encoding="utf-8").splitlines():
                try:
                    self._audit.append(AuditEvent.model_validate_json(line))
                except ValueError:
                    continue

    def _persist(self, item: StoredInvestigation) -> None:
        folder = self.data_dir / "investigations"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{item.report.investigation_id}.json").write_text(item.model_dump_json(indent=2), encoding="utf-8")

    def _append_audit(self, investigation_id: str, event: str, detail: dict[str, Any]) -> None:
        record = AuditEvent(event_id=len(self._audit) + 1, at=datetime.now(timezone.utc), investigation_id=investigation_id, event=event, detail=detail)
        self._audit.append(record)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with (self.data_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def add(self, report: InvestigationReport, persist: bool = True) -> None:
        with self._lock:
            item = StoredInvestigation(report=report)
            self._items[report.investigation_id] = item
            if not persist:
                return
            self._persist(item)
            self._append_audit(report.investigation_id, "investigation_completed", {
                "advisory_id": report.advisory.advisory_id,
                "advisory_sha256": report.advisory.content_sha256,
                "dataset_id": report.dataset.dataset_id,
                "dataset_version": report.dataset.version,
                "seed": report.seed,
                "model": report.model_run.model,
                "status": report.status,
                "tool_calls": len(report.trace),
                "selected_rule_id": report.selected_rule.rule_id if report.selected_rule else None,
            })

    def get(self, investigation_id: str) -> StoredInvestigation | None:
        return self._items.get(investigation_id)

    def list(self) -> list[InvestigationSummary]:
        items = sorted(self._items.values(), key=lambda item: item.report.created_at, reverse=True)
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
            for item in items
        ]

    def review(self, investigation_id: str, request: ReviewRequest) -> ReviewRecord:
        with self._lock:
            item = self._items.get(investigation_id)
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
            )
            item.reviews.append(record)
            if item.report.origin == "live":
                self._persist(item)
            self._append_audit(investigation_id, "review_recorded", {
                "decision": record.decision,
                "reviewer": record.reviewer,
                "rule_id": record.rule_id,
                "rule_version": record.rule_version,
                "activation": record.activation,
            })
            return record

    def audit(self, investigation_id: str | None = None) -> list[AuditEvent]:
        return [event for event in self._audit if investigation_id is None or event.investigation_id == investigation_id]
