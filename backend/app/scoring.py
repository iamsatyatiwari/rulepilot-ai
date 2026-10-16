"""Score individual transactions with the active rule set.

This stands in for the bank-side integration. The baseline and every
human-approved rule are active: any of them flagging decides ``flag``.
Shadow entries are still supported (evaluated, reported, never deciding)
for rules a bank wants to trial without enforcing them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.governance import CatalogEntry
from app.rules.engine import evaluate_rule
from app.rules.models import Rule, Transaction

SHADOW_NOTE = (
    "Approved rules are active and can decide. Shadow rules, if any, are evaluated for "
    "comparison and never change the decision."
)


class RuleVerdict(BaseModel):
    rule_id: str
    name: str
    version: int
    flagged: bool
    missing_fields: list[str]
    investigation_id: str | None = None
    technique: str | None = None


class TransactionScore(BaseModel):
    transaction_id: str | None
    decision: Literal["flag", "allow"]
    decided_by: list[str]
    active_rules: list[RuleVerdict]
    shadow_rules: list[RuleVerdict]
    shadow_flagged_by: list[str]
    caught_only_in_shadow: bool
    approved_flagged_by: list[str] = []
    caught_only_by_approved: bool = False
    note: str = SHADOW_NOTE


def _verdict(rule: Rule, transaction: Transaction, entry: CatalogEntry | None = None) -> RuleVerdict:
    missing = sorted({c.field for c in rule.conditions if getattr(transaction, c.field) is None})
    return RuleVerdict(
        rule_id=rule.rule_id,
        name=rule.name,
        version=rule.version,
        flagged=evaluate_rule(rule, transaction),
        missing_fields=missing,
        investigation_id=entry.investigation_id if entry else None,
        technique=entry.technique if entry else None,
    )


def score_transaction(
    transaction: Transaction,
    active_rules: list[Rule],
    shadow_entries: list[CatalogEntry],
    approved_entries: list[CatalogEntry] | None = None,
) -> TransactionScore:
    """Return the decision of the active rules (base rules + approved entries) and any shadow verdicts.

    The decision is ``flag`` when any active rule flags (rule-set OR). Missing
    features fail closed, as everywhere else in the engine.
    """
    approved = [_verdict(entry.rule, transaction, entry) for entry in approved_entries or []]
    base = [_verdict(rule, transaction) for rule in active_rules]
    active = base + approved
    shadow = [_verdict(entry.rule, transaction, entry) for entry in shadow_entries]
    decided_by = [verdict.rule_id for verdict in active if verdict.flagged]
    shadow_flagged_by = [verdict.rule_id for verdict in shadow if verdict.flagged]
    return TransactionScore(
        transaction_id=transaction.transaction_id,
        decision="flag" if decided_by else "allow",
        decided_by=decided_by,
        active_rules=active,
        shadow_rules=shadow,
        shadow_flagged_by=shadow_flagged_by,
        caught_only_in_shadow=not decided_by and bool(shadow_flagged_by),
        approved_flagged_by=[verdict.rule_id for verdict in approved if verdict.flagged],
        caught_only_by_approved=any(v.flagged for v in approved) and not any(v.flagged for v in base),
    )
