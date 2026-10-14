"""Structured inputs and outputs exchanged with the intelligence agent."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.rules.models import ComparisonOperator

ShortText = Annotated[StrictStr, Field(min_length=1, max_length=300)]

CoverageAssessment = Literal[
    "gap_identified",
    "covered_by_existing_rules",
    "not_testable_with_available_data",
    "insufficient_evidence",
]
AgentRecommendation = Literal["recommend_for_review", "do_not_recommend", "insufficient_evidence"]


class ConditionInput(BaseModel):
    """One candidate-rule condition proposed by the agent."""

    model_config = ConfigDict(extra="forbid")

    field: StrictStr = Field(description="A field name from get_rule_catalog's available_fields.")
    operator: ComparisonOperator
    value: float = Field(description="Numeric threshold.")


class AdvisoryFindings(BaseModel):
    """Structured extraction from an advisory. Quotes must be copied verbatim."""

    model_config = ConfigDict(extra="forbid")

    technique_name: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    summary: Annotated[StrictStr, Field(min_length=1, max_length=800)]
    behaviors: Annotated[list[ShortText], Field(max_length=8)]
    indicators: Annotated[list[ShortText], Field(max_length=8)]
    required_fields: Annotated[
        list[Annotated[StrictStr, Field(min_length=1, max_length=64)]], Field(max_length=12)
    ] = Field(
        description=(
            "Transaction data fields needed to test the behaviors. Use catalog field names when "
            "they exist; otherwise a short snake_case name for the missing field."
        )
    )
    testable_hypotheses: Annotated[list[ShortText], Field(max_length=5)]
    uncertainties: Annotated[list[ShortText], Field(max_length=6)]
    evidence_quotes: Annotated[list[ShortText], Field(max_length=5)] = Field(
        description="Short verbatim quotes from the advisory text that support the findings."
    )


class AgentConclusion(BaseModel):
    """The agent's assessment; deterministic code re-checks every claim."""

    model_config = ConfigDict(extra="forbid")

    coverage_assessment: CoverageAssessment
    selected_candidate_rule_id: StrictStr | None = Field(
        default=None,
        description="rule_id returned by evaluate_candidate_rule, or null when no candidate is supported.",
    )
    recommendation: AgentRecommendation
    rationale: Annotated[StrictStr, Field(min_length=1, max_length=1200)]
    limitations: Annotated[list[ShortText], Field(max_length=6)]
