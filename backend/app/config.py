"""Environment-driven settings. Secrets are read from the environment only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env", override=False)


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    gemini_model: str
    gemini_fallback_models: tuple[str, ...]
    agent_max_llm_calls: int
    agent_timeout_seconds: int
    cors_origins: tuple[str, ...]
    data_dir: Path
    static_dir: Path | None
    store: str
    gcp_project: str | None

    @property
    def gemini_configured(self) -> bool:
        uses_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}
        if uses_vertex:
            return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.environ.get(
        "RULEPILOT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    static = os.environ.get("RULEPILOT_STATIC_DIR")
    return Settings(
        gemini_model=os.environ.get("RULEPILOT_GEMINI_MODEL", "gemini-3.8-flash"),
        gemini_fallback_models=tuple(
            name.strip()
            for name in os.environ.get(
                "RULEPILOT_GEMINI_FALLBACK_MODELS",
                "gemini-flash-latest,gemini-3.6-flash,gemini-3.5-flash-lite",
            ).split(",")
            if name.strip()
        ),
        agent_max_llm_calls=_int("RULEPILOT_AGENT_MAX_LLM_CALLS", 12, 3, 25),
        agent_timeout_seconds=_int("RULEPILOT_AGENT_TIMEOUT_SECONDS", 120, 10, 300),
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        data_dir=Path(os.environ.get("RULEPILOT_DATA_DIR", BACKEND_DIR / ".rulepilot_data")),
        static_dir=Path(static) if static else None,
        store="firestore" if os.environ.get("RULEPILOT_STORE", "local").lower() == "firestore" else "local",
        gcp_project=os.environ.get("GOOGLE_CLOUD_PROJECT") or None,
    )
