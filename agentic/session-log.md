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
  - ✅ 96 backend / 13 frontend tests, tsc, build.
  - ✅ production-mode run + `backend/scripts/smoke_check.py` (24/24; 29/29 with `--review`).
  - ✅ Firestore emulator: smoke passes, no local files, state survives restart.
  - ✅ headless Chrome: Investigations and Transaction monitor, desktop + mobile, no errors.
  - ⏳ live Gemini runs — **needs a new `GOOGLE_API_KEY` from the user** in `backend/.env` (blanked locally).
  - ⏳ Docker image build — Docker not installed; user not yet asked/answered whether to install or rely on Cloud Build.
- **Fixed this session:** review banner now shows the human decision; scheduled runs labelled.
- **Still open:** `config.py` treats the `.env.example` placeholder key as configured (low priority).
- **Next step:** user provides Gemini key → live investigation + learning loop + ingestion with token locally → deploy (needs GCP project ID + billing; Cloud Scheduler steps are in `skills.md` skill 9).
- **Git:** this session's work is committed on `feat/shadow-scoring-ingestion`. Neither `main` nor this branch is pushed yet: this Mac has no GitHub credentials (HTTPS prompt fails; SSH key `~/.ssh/id_ed25519` is not on the GitHub account).

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
