# Architecture

## Responsibilities

| Layer | Responsibility | Code |
| --- | --- | --- |
| Intelligence | Curated or pasted advisories, hashing, quote verification | `backend/app/intel/` |
| Agent orchestration | One ADK agent, prompt, retries and fallback, deterministic post-checks | `backend/app/agent/` |
| Deterministic engine | Rule schema, evaluation, metrics, datasets, splits, discovery, backtests | `backend/app/rules/`, `evaluation.py`, `data.py`, `datasets.py`, `discovery.py`, `backtest.py` |
| Governance | Investigation store, review decisions, reviewed rule catalog, review history, audit log | `backend/app/governance.py`, `backend/app/storage.py` |
| HTTP | Versioned API, static dashboard in production | `backend/app/main.py`, `api.py`, `investigations_api.py` |
| UI | Investigations workspace and rule-engine view | `frontend/src/` |

## Investigation flow

```mermaid
sequenceDiagram
    participant UI as Dashboard
    participant API as FastAPI
    participant O as Orchestrator
    participant A as ADK agent (Gemini)
    participant T as Tools
    participant E as Rule engine
    participant G as Governance store

    UI->>API: POST /api/v1/investigations
    API->>O: run_investigation(advisory, dataset, seed)
    O->>A: delimited advisory + instructions
    O->>G: approved rules + review history
    A->>T: get_rule_catalog / get_review_history / check_field_coverage / get_training_profile
    A->>T: evaluate_candidate_rule (≤3, validation only)
    T->>E: validate rule, compute metrics
    A->>T: submit_findings
    O->>O: verify quotes, recompute coverage, guardrails
    O->>E: run_final_holdout (once, test split)
    O-->>API: InvestigationReport
    API->>G: store + audit "investigation_completed"
    UI->>API: POST /investigations/{id}/review
    API->>G: record decision + audit "review_recorded"
    G->>G: approve adds rule to catalog (inactive); reject or changes removes it
```

## Backend module map

| Module | Purpose |
| --- | --- |
| `rules/models.py` | `Transaction` (ruleable fields marked by metadata), `Condition`, `Rule`, operators, statuses |
| `rules/engine.py` | `evaluate_rule` — explicit operators, fail-closed on missing data |
| `evaluation.py` | `calculate_metrics` confusion matrix |
| `data.py` | `create_synthetic_dataset` (v1), `create_card_scenario_dataset` (v2), stratified split |
| `datasets.py` | Registry: `synthetic-v1`, `card-scenario-v2`; `populated_fields` |
| `baseline.py` | `RP-BASELINE-001` |
| `discovery.py` | Threshold discovery (M2A) |
| `backtest.py` | `compare_records` / `compare_on_split` → baseline, candidate, combined metrics |
| `agent/schemas.py` | `ConditionInput`, `AdvisoryFindings`, `AgentConclusion` |
| `agent/tools.py` | `InvestigationContext`, `InvestigationToolkit`, `coverage_for_fields`, `run_final_holdout` |
| `agent/agent.py` | Prompt, `build_user_message`, `run_adk_agent` with retry and fallback |
| `agent/orchestrator.py` | `run_investigation`, `InvestigationReport`, guardrails, status |
| `intel/advisories.py` | `Advisory`, loader, `verify_quotes` |
| `intel/advisories/*.json` | Curated sources |
| `intel/recorded/*.json` | Real past runs shown as "recorded" |
| `governance.py` | `GovernanceStore` (investigations, reviews, `catalog()`, `approved_rules()`, `review_history()`, audit) |
| `storage.py` | `DocumentBackend`: `LocalJsonBackend` and `FirestoreBackend` (records stored as JSON strings) |
| `config.py` | Environment settings; loads `backend/.env` |

## API reference (`/api/v1`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/info` | API identity and version |
| GET | `/datasets` | Dataset registry |
| GET | `/rules` | Rule catalog (baseline) |
| POST | `/rules/evaluate` | Evaluate a supplied rule on v1 records |
| POST | `/rules/discover` | Threshold discovery (`dataset_id` optional) |
| POST | `/backtests/run` | Baseline vs candidate on test split (`dataset_id` optional) |
| GET | `/advisories` | Curated advisories with hashes |
| GET | `/agent/status` | Whether Gemini is configured; model and bounds (never secrets) |
| POST | `/investigations` | `{advisory_id}` or `{custom_advisory}`, `dataset_id`, `seed` |
| GET | `/investigations` | Summaries, newest first |
| GET | `/investigations/{id}` | Report and reviews |
| POST | `/investigations/{id}/review` | `{decision, reviewer, comment}` |
| GET | `/rule-catalog` | Active baseline + approved (not active) rules with provenance |
| GET | `/audit` | Audit events, optional `investigation_id` |

`/health` is outside the prefix. Interactive docs: `http://127.0.0.1:8000/docs`.

Status codes used by investigations: 404 unknown advisory, 409 nothing to review, 422 invalid input, 429 capacity busy, 503 Gemini not configured.

## Configuration (`backend/.env`, see `.env.example`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | — | Gemini API key (secret) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | `TRUE` to use Vertex AI with ADC |
| `RULEPILOT_GEMINI_MODEL` | `gemini-3.8-flash` | Primary model |
| `RULEPILOT_GEMINI_FALLBACK_MODELS` | `gemini-flash-latest,gemini-3.6-flash,gemini-3.5-flash-lite` | Tried on 429/503 |
| `RULEPILOT_AGENT_MAX_LLM_CALLS` | `12` | Per attempt (3–25) |
| `RULEPILOT_AGENT_TIMEOUT_SECONDS` | `120` | Whole run (10–300) |
| `RULEPILOT_CORS_ORIGINS` | localhost:5173 | Split local mode only |
| `RULEPILOT_STORE` | `local` | `local` JSON files or `firestore` |
| `GOOGLE_CLOUD_PROJECT` | — | Firestore project (with `RULEPILOT_STORE=firestore`) |
| `RULEPILOT_DATA_DIR` | `backend/.rulepilot_data` | Local store and audit log |
| `RULEPILOT_STATIC_DIR` | unset | Built dashboard path; set in Docker |

Frontend: `VITE_API_BASE_URL` (dev default `http://localhost:8000`; production builds use the same origin).

## Continuous learning (governed)

The model is never retrained. The *system* learns through reviewed state:

1. A reviewer approves a candidate → it is stored in the rule catalog as `approved`, `activation: not_activated`.
2. The next investigation compares candidates against the **reference rule set** = baseline OR every approved rule (`compare_records(..., reference_rules)`), and coverage lists their fields.
3. `get_review_history` gives the agent the last 10 decisions (decision, comment ≤ 300 chars, conditions, held-out deltas) as untrusted data.
4. If existing rules already detect the behaviour, the agent concludes `covered_by_existing_rules` and proposes nothing.
5. A later reject or request-changes decision removes the rule from the catalog. Every step is audited.

## Deployment shape

One Cloud Run service built from the root `Dockerfile`: stage 1 builds the Vite app, stage 2 installs `requirements-lock.txt`, copies `backend/app` and the built `static/`. FastAPI serves `/api/*`, `/health`, `/assets/*`, and falls back to `index.html`.
