"""Rule lab: explain a rule on one transaction, generate examples for or against it, keep test cases.

Everything here is deterministic code. Examples are built from the rule's own
conditions (no model, no randomness), so analysts can see exactly why a
transaction is or is not flagged and save hand-made labelled cases. Customer
fraud reports from the demo bank are stored in the same collection with
``source="customer_report"``.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.rules.engine import _compare as compare
from app.rules.engine import evaluate_rule
from app.rules.models import ComparisonOperator, Condition, LogicalOperator, Rule, Transaction
from app.storage import DocumentBackend

TEST_CASES = "test_cases"
MAX_TEST_CASES = 500
CaseSource = Literal["analyst", "customer_report"]
Label = Literal["fraud", "legit"]

# A plain everyday payment; generated examples start here and change only what the rule checks.
NEUTRAL = Transaction(
    transaction_id="LAB-EXAMPLE",
    amount=42.0,
    account_age_days=1500,
    transactions_24h=2,
    distance_from_home_km=5.0,
    transactions_1h=0,
    declined_attempts_24h=0,
    card_present=1,
    hour_of_day=14,
    new_device=0,
    days_since_sim_change=900,
    credential_resets_24h=0,
    new_payee=0,
)
BINARY_FIELDS = {"card_present", "new_device", "new_payee"}
INTEGER_FIELDS = {
    "account_age_days", "transactions_24h", "transactions_1h", "declined_attempts_24h",
    "hour_of_day", "days_since_sim_change", "credential_resets_24h", *BINARY_FIELDS,
}
FIELD_MAX = {"hour_of_day": 23, **{name: 1 for name in BINARY_FIELDS}}


class ConditionCheck(BaseModel):
    field: str
    operator: str
    threshold: float
    value: float | None
    passed: bool | None  # None when the field is missing (the rule fails closed)


class Explanation(BaseModel):
    rule_id: str
    logical_operator: str
    flagged: bool
    conditions: list[ConditionCheck]


class TestCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    transaction: Transaction
    expected: Label
    note: Annotated[StrictStr, Field(max_length=500)] = ""
    created_by: Annotated[StrictStr, Field(min_length=1, max_length=100)] = "analyst"


class TestCase(TestCaseInput):
    case_id: str
    source: CaseSource = "analyst"
    created_at: datetime


class CaseResult(BaseModel):
    case: TestCase
    flagged: bool
    passed: bool


class RunSummary(BaseModel):
    rule_id: str
    cases: int
    passed: int
    fraud_cases: int
    fraud_caught: int
    legit_cases: int
    false_alarms: int
    results: list[CaseResult]


def explain(rule: Rule, transaction: Transaction) -> Explanation:
    checks = []
    for condition in rule.conditions:
        value = getattr(transaction, condition.field)
        passed = None if value is None else compare(value, condition.operator, condition.value)
        checks.append(ConditionCheck(
            field=condition.field, operator=condition.operator.value, threshold=float(condition.value),
            value=None if value is None else float(value), passed=passed,
        ))
    return Explanation(
        rule_id=rule.rule_id, logical_operator=rule.logical_operator.value,
        flagged=evaluate_rule(rule, transaction), conditions=checks,
    )


def _fit(field: str, value: float) -> int | float:
    value = max(0.0, min(value, FIELD_MAX.get(field, value)))
    return int(round(value)) if field in INTEGER_FIELDS else round(value, 2)


def _satisfy(condition: Condition) -> int | float:
    v, op, field = float(condition.value), condition.operator, condition.field
    step = 1 if field in INTEGER_FIELDS else max(0.01, abs(v) * 0.1)
    targets = {
        ComparisonOperator.GREATER_THAN: v + step,
        ComparisonOperator.GREATER_THAN_OR_EQUAL: v if field not in INTEGER_FIELDS else float(int(-(-v // 1))),
        ComparisonOperator.LESS_THAN: v - step,
        ComparisonOperator.LESS_THAN_OR_EQUAL: v,
        ComparisonOperator.EQUALS: v,
        ComparisonOperator.NOT_EQUALS: v + 1 if field not in BINARY_FIELDS else 1 - v,
    }
    return _fit(field, targets[op])


def _violate(condition: Condition) -> int | float:
    flipped = {
        ComparisonOperator.GREATER_THAN: ComparisonOperator.LESS_THAN_OR_EQUAL,
        ComparisonOperator.GREATER_THAN_OR_EQUAL: ComparisonOperator.LESS_THAN,
        ComparisonOperator.LESS_THAN: ComparisonOperator.GREATER_THAN_OR_EQUAL,
        ComparisonOperator.LESS_THAN_OR_EQUAL: ComparisonOperator.GREATER_THAN,
        ComparisonOperator.EQUALS: ComparisonOperator.NOT_EQUALS,
        ComparisonOperator.NOT_EQUALS: ComparisonOperator.EQUALS,
    }[condition.operator]
    return _satisfy(condition.model_copy(update={"operator": flipped}))


def generate_example(rule: Rule, match: bool) -> Transaction:
    """Build a transaction the rule flags (``match``) or does not flag, changing only checked fields.

    For a non-match under AND, one condition is broken and the rest still hold,
    which makes a "near miss"; under OR, every condition is broken.
    """
    values = NEUTRAL.model_dump()
    for condition in rule.conditions:
        values[condition.field] = _satisfy(condition)
    if not match:
        targets = rule.conditions[:1] if rule.logical_operator is LogicalOperator.AND else rule.conditions
        for condition in targets:
            values[condition.field] = _violate(condition)
    example = Transaction.model_validate({**values, "transaction_id": f"LAB-{'MATCH' if match else 'MISS'}"})
    if evaluate_rule(rule, example) != match:
        raise ValueError("this rule's conditions cannot all be met by one transaction")
    return example


class TestCaseStore:
    """Labelled test cases (analyst-made or customer-reported), persisted with the governance backend."""

    def __init__(self, backend: DocumentBackend) -> None:
        self.backend = backend
        self._lock = threading.Lock()

    def add(self, data: TestCaseInput, source: CaseSource = "analyst") -> TestCase:
        with self._lock:
            if len(self.backend.all(TEST_CASES)) >= MAX_TEST_CASES:
                raise ValueError(f"at most {MAX_TEST_CASES} test cases can be stored")
            case = TestCase(
                **data.model_dump(exclude={"transaction"}),
                # The label lives in ``expected``; the transaction itself carries none.
                transaction=data.transaction.model_copy(update={"ground_truth_fraud": None}),
                case_id=f"case-{uuid.uuid4().hex[:12]}", source=source, created_at=datetime.now(timezone.utc),
            )
            self.backend.put(TEST_CASES, case.case_id, {"payload": case.model_dump_json()})
            return case

    def list(self, source: CaseSource | None = None) -> list[TestCase]:
        cases = []
        for document in self.backend.all(TEST_CASES):
            try:
                cases.append(TestCase.model_validate_json(document["payload"]))
            except (KeyError, ValueError):
                continue
        return sorted((c for c in cases if source is None or c.source == source), key=lambda c: c.created_at)

    def delete(self, case_id: str) -> bool:
        with self._lock:
            if self.backend.get(TEST_CASES, case_id) is None:
                return False
            self.backend.delete(TEST_CASES, case_id)
            return True


def run_cases(rule: Rule, cases: list[TestCase]) -> RunSummary:
    results = []
    for case in cases:
        flagged = evaluate_rule(rule, case.transaction)
        results.append(CaseResult(case=case, flagged=flagged, passed=flagged == (case.expected == "fraud")))
    fraud = [r for r in results if r.case.expected == "fraud"]
    legit = [r for r in results if r.case.expected == "legit"]
    return RunSummary(
        rule_id=rule.rule_id, cases=len(results), passed=sum(r.passed for r in results),
        fraud_cases=len(fraud), fraud_caught=sum(r.flagged for r in fraud),
        legit_cases=len(legit), false_alarms=sum(r.flagged for r in legit), results=results,
    )


_stores: dict[int, TestCaseStore] = {}


def case_store(backend: DocumentBackend) -> TestCaseStore:
    """One test-case store per governance backend, so cases persist where reviews do."""
    if id(backend) not in _stores:
        _stores[id(backend)] = TestCaseStore(backend)
    return _stores[id(backend)]
