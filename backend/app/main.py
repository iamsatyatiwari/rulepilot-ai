"""HTTP API for RulePilot AI."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.bank_api import router as bank_router
from app.lab_api import router as lab_router
from app.config import get_settings
from app.investigations_api import router as investigations_router
from app.transactions_api import router as transactions_router

API_VERSION = "0.3.0"
settings = get_settings()

app = FastAPI(
    title="RulePilot AI API",
    description=(
        "Continuous financial rule intelligence: a bounded Gemini agent investigates "
        "intelligence, while a deterministic engine validates and backtests candidate rules."
    ),
    version=API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", tags=["status"])
def health() -> dict[str, str]:
    """Report API process availability."""
    return {"status": "ok"}


@app.get("/api/v1/info", tags=["status"])
def info() -> dict[str, str]:
    """Describe the API; used by the dashboard in both local and deployed modes."""
    return {"name": "RulePilot AI API", "status": "ready", "version": API_VERSION, "health": "/health"}


app.include_router(api_router)
app.include_router(investigations_router)
app.include_router(transactions_router)
app.include_router(bank_router)
app.include_router(lab_router)

static_dir = settings.static_dir
if static_dir is not None and (static_dir / "index.html").is_file():
    # Same-origin deployment: serve the built dashboard and fall back to index.html.
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
else:

    @app.get("/", tags=["status"])
    def root() -> dict[str, str]:
        """Describe the API and point to its health endpoint."""
        return {"name": "RulePilot AI API", "status": "ready", "health": "/health"}
