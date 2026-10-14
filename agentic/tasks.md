# Tasks and milestones

Status values: `done`, `in progress`, `todo`, `deferred`.

## M3 — Gemini intelligence agent

| ID | Task | Status |
| --- | --- | --- |
| T0 | Upgrade FastAPI/Starlette; add google-adk 2.10.0 | done |
| T1 | Dataset registry; `card-scenario-v2` | done |
| T2 | Deterministic tools; shared backtest; single held-out | done |
| T3 | Curated advisories; quote verification | done |
| T4 | ADK agent, orchestrator, guardrails, retry/fallback | done |
| T5 | Investigations, review, audit API | done |
| T6 | Investigations UI | done |
| T7 | Local live end-to-end run; recorded runs | done |
| T8 | Cloud Run deployment | todo — needs GCP project, billing, gcloud |
| T9 | README and architecture diagram (done 15 Oct); PDF deck, 3-minute video | in progress |

## M4 — Continuous learning (governed)

| ID | Task | Status |
| --- | --- | --- |
| L1 | Approved rules join the rule catalog (approved, inactive, versioned); coverage and comparisons include them | done |
| L2 | `get_review_history` tool: prior decisions and comments as untrusted data | done |
| L3 | Firestore-backed `GovernanceStore` for Cloud Run persistence | done (fake-client tested; verify on GCP at deploy) |
| L4 | Golden-set evaluation: `app/golden.py`, `scripts/golden_eval.py` | done |
| L8 | `payments-scenario-v3`: 30k rows, device/SIM/credential/payee fields, injected SIM-swap takeover | done |
| L5 | Scheduled ingestion: token-protected `/ingestion/run` for Cloud Scheduler | done (local); create the Scheduler job at deploy |
| L7 | Shadow scoring: mock bank feed, `/transactions/score` and `/transactions/simulate`, Transaction monitor UI | done |
| L6 | Re-backtest approved rules on new data windows (drift) | deferred |

## Deferred beyond the prototype

Authentication and reviewer identity · rule activation workflow · real transaction data · AML / account takeover / scam typologies · multi-agent workflows.

## Definition of done (every task)

1. Behaviour covered by tests that do not call Gemini.
2. All checks in [skills.md](skills.md) skill 2 pass.
3. [guardrails.md](guardrails.md) still hold.
4. `context.md` status, this file, and `IMPLEMENTATION_SUMMARY.txt` updated.
