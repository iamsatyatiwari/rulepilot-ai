# Session log — resume work across context windows

This file carries working state from one AI-assistant session (context window) to the next. `CLAUDE.md` imports it, so Claude Code loads it automatically at the start of every session; other assistants are pointed here by `AGENTS.md`.

**Rules**

- Update **Current handoff** whenever a unit of work finishes, before a long-running step, and at the end of every session. Overwrite it; it describes *now*.
- Add one entry to **Log** per session (newest first). Keep entries short: what changed, why, what is left.
- Durable facts belong elsewhere: status in `context.md`, tasks in `tasks.md`, procedures in `skills.md`. This file is for in-flight work.
- No secrets, API keys, or personal data (see [guardrails.md](guardrails.md)).

---

## Current handoff

- **Branch:** `feat/shadow-scoring-ingestion`, created from `main` after `feat/m3-intelligence-agent` was fast-forward merged into `main` locally (14 Oct).
- **Phase:** local testing and small features before Cloud Run deploy. Deadline 18 Oct 2026, team target 17 Oct — see `PROJECT_STATUS.md`.
- **Decided with user (14 Oct):** no real banking integration. Instead (a) mock bank feed + shadow scoring to show the engine catching new-rule fraud, (b) scheduled ingestion endpoint for Cloud Scheduler (the "cron job" in the user's sketch). Both **done locally**.
- **Local test status:**
  - ✅ 98 backend / 13 frontend tests, tsc, build; production-mode + Firestore-emulator smoke checks; headless Chrome.
  - ✅ Docker (Colima) installed; `docker build -t rulepilot-ai:local .` succeeds (Python 3.11 image).
  - ✅ Live Gemini (14 Oct 17:41): card testing → `pending_human_review`, recall +43.6 pp, all guardrails pass; SIM swap → `not_testable`.
- **Gemini key facts:** key is in `backend/.env` only. It gets 429 on `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`, and often `gemini-3.5-flash`; only `gemini-3.5-flash-lite` reliably works → **billing is probably not enabled** on the key's project. Local `.env` uses `RULEPILOT_GEMINI_MODEL=gemini-3.5-flash`, fallback `gemini-3.5-flash-lite`. For Cloud Run, enable billing or set the same env vars.
- **Fixed:** a stalled model request could hang ~7 min past the 120 s limit (ADK waits for the in-flight call on cancel). Each request now has an HTTP timeout (`request_timeout_ms`, ≤ 45 s) and timeouts count as transient → fallback.
- **Repo location:** moved from `~/Documents/git_projects/rulepilot-ai` (iCloud-synced; caused `"<name> 2.<ext>"` duplicate files) to **`~/dev/rulepilot-ai`** on 14 Oct. `backend/.venv` was recreated there. If `pytest` ever reports ~144 tests, look for `* 2.py` copies.
- **GitHub:** `gh` CLI logged in as `shuklapiyush113` (HTTPS, credential helper set up). Git identity: `Piyush Shukla <91715671+shuklapiyush113@users.noreply.github.com>` (global).
- **Git state:** `shuklapiyush113` is a collaborator (write). Pushed 14 Oct: `main` → `74dfbab` (fast-forward), `feat/shadow-scoring-ingestion` (tracks origin). **Draft PR #1** (https://github.com/iamsatyatiwari/rulepilot-ai/pull/1) into `main`, awaiting user review — do not mark ready or merge without the user.
- **Next step:** user reviews draft PR #1 → deploy to Cloud Run (needs GCP project ID + billing).

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
