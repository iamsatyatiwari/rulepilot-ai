# Session log — resume work across context windows

This file carries working state from one AI-assistant session (context window) to the next. `CLAUDE.md` imports it, so Claude Code loads it automatically at the start of every session; other assistants are pointed here by `AGENTS.md`.

**Rules**

- Update **Current handoff** whenever a unit of work finishes, before a long-running step, and at the end of every session. Overwrite it; it describes *now*.
- Add one entry to **Log** per session (newest first). Keep entries short: what changed, why, what is left.
- Durable facts belong elsewhere: status in `context.md`, tasks in `tasks.md`, procedures in `skills.md`. This file is for in-flight work.
- No secrets, API keys, or personal data (see [guardrails.md](guardrails.md)).

---

## Current handoff

- **Branches:** `feat/shadow-scoring-ingestion` = draft→ready PR #1 (https://github.com/iamsatyatiwari/rulepilot-ai/pull/1), **not merged** — the merge command was blocked by the permission classifier; the user merges it on GitHub or allows `gh pr merge`. `feat/dataset-v3` branches from it (local commit, not pushed) — open a PR into `main` after #1 merges.
- **Phase:** local development before Cloud Run deploy. Deadline 18 Oct 2026, team target 17 Oct — see `PROJECT_STATUS.md` (stale: still says the M3 branch is unmerged and 82 tests; refresh with the README rewrite).
- **Done 14 Oct (feat/dataset-v3):** `payments-scenario-v3` (30k rows, 202 held-out fraud vs 39 on v2), 5 new fields, injected SIM-swap takeover, default for investigations/ingestion; mock feed and monitor UI updated; golden set (L4) `app/golden.py` + `scripts/golden_eval.py`. 110 backend / 14 frontend tests, tsc, build pass. Live golden run: both v3 cases PASS (flash-lite fallback).
- **Open decision for the user:** ~79% of injected takeovers are ≥ 1,500 (training split), so the baseline already catches most; a SIM-swap rule adds only ~3 pp held-out recall. Option: draw takeover amounts mostly below the baseline threshold (realistic "stay under limits" behaviour), judged on train/validation only, then re-run the golden set.
- **Recorded demo runs** are still on `card-scenario-v2`; refresh them on v3 (skill 8) once the key has quota.
- **Gemini key facts:** key is in `backend/.env` only. Free tier: 20 requests/day per model; 429 on `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`, often `gemini-3.5-flash`; `gemini-3.5-flash-lite` works → enable billing before the demo/Cloud Run.
- **Untracked `requirements.txt` at repo root:** VS Code Docker scaffold (fastapi 0.109, gunicorn) that conflicts with `backend/requirements-lock.txt`; left uncommitted, suggest deleting.
- **Repo location:** `~/dev/rulepilot-ai` (moved off iCloud). If `pytest` ever reports far too many tests, look for `* 2.py` copies.
- **GitHub:** `gh` logged in as `shuklapiyush113` (collaborator, write). Repo is public.
- **Next steps:** user merges PR #1 → push `feat/dataset-v3` + PR → decide the takeover-amount question → README rewrite + PROJECT_STATUS refresh → Cloud Run deploy (needs GCP project ID + billing) → deck → video.

## Local environment (macOS)

`skills.md` documents Windows PowerShell. On this macOS machine the equivalents are:

```bash
# backend (Python 3.14 venv; project requires >=3.11)
cd backend
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend
cd frontend && npm ci && npm run dev

# production-mode run (same layout as the Docker image), then smoke test
cd backend && RULEPILOT_STATIC_DIR=$PWD/../frontend/dist RULEPILOT_DATA_DIR=/tmp/rpdata \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
.venv/bin/python scripts/smoke_check.py http://127.0.0.1:8080 --review   # --review writes review/audit records

# Firestore emulator (Java 21 is installed; firebase-tools 13.x fails on Node 26, use 15.31.0)
#   firebase.json: {"emulators":{"firestore":{"host":"127.0.0.1","port":8085},"ui":{"enabled":false}}}
npx -y firebase-tools@15.31.0 emulators:start --only firestore --project demo-rulepilot
# then start uvicorn with: FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 GOOGLE_CLOUD_PROJECT=demo-rulepilot RULEPILOT_STORE=firestore

# skill 2 checks
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm test && npx tsc -b --pretty false && npm run build
git diff --check
```

## Log

### 2026-10-14 — dataset v3 and golden set
- PR #1 merge blocked by the permission classifier; built on `feat/dataset-v3` instead.
- Added v3 dataset, new fields, SIM-swap takeover pattern, feed/monitor updates, golden-set module, script and tests; docs updated (architecture, skills 6/7, ui-guide, context, tasks L4/L8, IMPLEMENTATION_SUMMARY).
- Live golden run passes on v3; found that the baseline already catches most injected takeovers (open decision above).

### 2026-10-14 — repo move and GitHub setup
- Moved repo to `~/dev/rulepilot-ai`; installed `gh`, logged in as `shuklapiyush113`; set git identity; re-authored the two unpushed commits. Push waits on collaborator access.

### 2026-10-14 — merge, Docker, live Gemini
- Fast-forward merged `feat/m3-intelligence-agent` into `main` (local), branched `feat/shadow-scoring-ingestion`, committed. Push blocked (no credentials).
- Installed Colima + Docker; image builds. Live runs work after the per-request timeout fix; key lacks quota for newer models.

### 2026-10-14 — shadow scoring and scheduled ingestion
- User's hand-drawn architecture compared with the code: AI → rule generation → engine matches; banking connection, cron job, and auto-activation do not (human gate is by design).
- Added `app/scoring.py`, `app/transactions_api.py`, `create_demo_feed`, `/ingestion/run` (token), `MonitorView.tsx`, banner fix; docs updated (architecture, skills 9/11, ui-guide, tasks L5/L7, context, guardrail 13, IMPLEMENTATION_SUMMARY).
- Renamed smoke script to `smoke_check.py` (pytest was collecting `*_test.py`).

### 2026-10-14 — local pre-deploy testing
- Read `PROJECT_STATUS.md`: remaining = deploy, README rewrite, merge/push public, deck, video.
- Production-mode, Firestore-emulator, and headless-Chrome tests all pass (details in Current handoff). Added `backend/scripts/smoke_check.py`.
- Found the review-banner inconsistency and the placeholder-key issue (not yet fixed).
- No Docker or gcloud on this Mac; no Gemini key yet.

### 2026-10-14 — environment setup
- Pulled origin; checked out `feat/m3-intelligence-agent` (commits `00e421c`, `2f05c23`, `74dfbab`: Gemini ADK agent, governed learning, project status).
- Created `backend/.venv` with Python 3.14.7 and installed `requirements-lock.txt` (`pip check` clean). Ran `npm ci` in `frontend` (Node 26.8.1).
- Checks: backend 82 passed (1 expected Starlette deprecation warning); frontend 10 passed; `tsc` clean; build OK.
- Added this session-log system.
