"""Load curated advisories and verify evidence quotes against their text."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictStr

ADVISORY_DIR = Path(__file__).parent / "advisories"
MAX_ADVISORY_CHARS = 20_000

SourceType = Literal["government_psa", "regulatory_advisory", "industry_guidance", "analyst_supplied"]


class Advisory(BaseModel):
    """An intelligence document. Its text is untrusted data, never instructions."""

    model_config = ConfigDict(extra="forbid")

    advisory_id: Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")]
    title: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    publisher: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    source_url: HttpUrl
    published_date: StrictStr | None = None
    retrieved_at: StrictStr
    source_type: SourceType
    rights_note: Annotated[StrictStr, Field(max_length=300)]
    excerpt: Annotated[StrictStr, Field(min_length=20, max_length=MAX_ADVISORY_CHARS)]

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.excerpt.encode("utf-8")).hexdigest()


class AdvisorySummary(BaseModel):
    advisory_id: str
    title: str
    publisher: str
    source_url: str
    published_date: str | None
    retrieved_at: str
    source_type: str
    rights_note: str
    content_sha256: str
    excerpt: str


def summarize(advisory: Advisory) -> AdvisorySummary:
    return AdvisorySummary(
        **advisory.model_dump(mode="json"), content_sha256=advisory.content_sha256
    )


@lru_cache(maxsize=1)
def load_curated_advisories() -> dict[str, Advisory]:
    advisories: dict[str, Advisory] = {}
    for path in sorted(ADVISORY_DIR.glob("*.json")):
        advisory = Advisory.model_validate(json.loads(path.read_text(encoding="utf-8")))
        advisories[advisory.advisory_id] = advisory
    return advisories


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-"}))
    return re.sub(r"\s+", " ", text).strip().casefold()


def verify_quotes(quotes: list[str], source_text: str) -> list[dict[str, object]]:
    """Mark each quote as verified only if it appears verbatim (whitespace-insensitive)."""
    haystack = _normalize(source_text)
    return [
        {"quote": quote, "verified": bool(_normalize(quote)) and _normalize(quote) in haystack}
        for quote in quotes
    ]
