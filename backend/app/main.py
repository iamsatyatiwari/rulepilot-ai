"""HTTP API for RulePilot AI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router

app = FastAPI(
    title="RulePilot AI API",
    description=(
        "A deterministic, synthetic-data rule engine foundation for continuous "
        "financial rule intelligence."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/", tags=["status"])
def root() -> dict[str, str]:
    """Describe the API and point to its health endpoint."""
    return {"name": "RulePilot AI API", "status": "ready", "health": "/health"}


@app.get("/health", tags=["status"])
def health() -> dict[str, str]:
    """Report API process availability."""
    return {"status": "ok"}


app.include_router(api_router)
