# Session log — resume work across context windows

This file carries working state from one AI-assistant session (context window) to the next. `CLAUDE.md` imports it, so Claude Code loads it automatically at the start of every session; other assistants are pointed here by `AGENTS.md`.

**Rules**

- Update **Current handoff** whenever a unit of work finishes, before a long-running step, and at the end of every session. Overwrite it; it describes *now*.
- Add one entry to **Log** per session (newest first). Keep entries short: what changed, why, what is left.
- Durable facts belong elsewhere: status in `context.md`, tasks in `tasks.md`, procedures in `skills.md`. This file is for in-flight work.
- No secrets, API keys, or personal data (see [guardrails.md](guardrails.md)).

---

## Current handoff

- **Branches:** PRs #1–#3 merged into `main` (`82b44e6`). `feat/sparkov-mock-bank` = Sparkov dataset + demo bank + simplified UI + docs; draft PR into `main`, awaiting user merge (`gh pr merge` is blocked by the classifier — user merges on GitHub).
- **Phase:** local development before Cloud Run deploy. Deadline 18 Oct 2026, team target 17 Oct — see `PROJECT_STATUS.md` (stale: still says the M3 branch is unmerged and 82 tests; refresh with the README rewrite).
- **Done 14 Oct (feat/dataset-v3):** `payments-scenario-v3` (30k rows, 202 held-out fraud vs 39 on v2), 5 new fields, injected SIM-swap takeover, default for investigations/ingestion; mock feed and monitor UI updated; golden set (L4) `app/golden.py` + `scripts/golden_eval.py`. 110 backend / 14 frontend tests, tsc, build pass. Live golden run: both v3 cases PASS (flash-lite fallback).
- **Done 15 Oct (same branch, PR #2):** takeover amounts redrawn so ~80% stay under 1,500 (judged on train/validation: baseline OR SIM rule recall 33% → 45–48%). Recorded demo runs refreshed live on v3: card testing (+5.4 pp), SIM swap testable (+10.8 pp), covered-after-approval; v2 SIM-swap `not_testable` recording kept. 112 backend / 14 frontend tests.
- **Gemini quota (15 Oct):** stronger models still 429/503 the next morning; every live run used `gemini-3.5-flash-lite` fallback. About 22 flash-lite requests used today. Billing is still needed before the demo.
- **Gemini key facts:** key is in `backend/.env` only. Free tier: 20 requests/day per model; 429 on `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`, often `gemini-3.5-flash`; `gemini-3.5-flash-lite` works → enable billing before the demo/Cloud Run.
- **Repo location:** `~/dev/rulepilot-ai` (moved off iCloud). If `pytest` ever reports far too many tests, look for `* 2.py` copies.
- **GitHub:** `gh` logged in as `shuklapiyush113` (collaborator, write). Repo is public.
- **Done 15 Oct afternoon:** `sparkov-cards-v1` (Sparkov run in an isolated venv in the session scratchpad; not in the repo), demo bank, Start here guide, summary-first investigations, ui-guide step-by-step. 123 backend / 18 frontend tests; local production-mode end-to-end verified.
- **Done 16 Oct:** approval activates rules (user chose this over a separate activation step); Rule lab; customer fraud reports + digest investigations (scheduled job and button). 133 backend / 21 frontend tests. Local servers: backend :8000, frontend :5173.
- **User's "caller ban"** = the cron job fetching public fraud reports. Done 16 Oct: FBI IC3 PSA feed (`app/intel/feeds.py`), plus customer reports. FTC has no usable RSS feed. "Test against data" moved under Advanced options.
- **User's architecture image** is not available in this conversation (it was in an earlier session); ask them to re-attach to compare box by box.
- **Next steps:** user merges the Sparkov/demo-bank PR → enable billing + GCP project ID + `gcloud` (not installed) → Cloud Run deploy (skill 9) → README live URL → deck → video.

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

### 2026-10-16 — public alert feeds
- Clarified "caller ban" = cron fetching public fraud reports. Built IC3 feed fetching; live check stored 4 alerts. 139 backend / 22 frontend tests.

### 2026-10-16 — activation, rule lab, customer reports
- User: approval should activate rules; wanted manual test data with the rule side by side; "caller ban" = cron fetching new frauds + customer reports.
- Built all three (except public-feed fetching). Fixed confusing review UX (double approvals).

### 2026-10-15 — Sparkov data, demo bank, simpler UI
- User asked to use Claude instead of Gemini: declined (competition requires Google models). Chose the Sparkov generator (MIT) over Kaggle downloads (licences unverifiable).
- Added sparkov-cards-v1, demo bank, Start here, summary-first report, docs.

### 2026-10-15 — README and status
- Deleted stray root `requirements.txt`. PR #2 merge blocked by the classifier. Rewrote README (judge-facing) and PROJECT_STATUS (current numbers, checklist, video script with SIM swap and monitor).

### 2026-10-15 — takeover amounts and recorded runs
- Redrew SIM-swap takeover amounts (mostly < 1,500); re-recorded 3 demo runs live on v3; golden tests now cover the recordings.

### 2026-10-14 — dataset v3 and golden set
- PR #1 merge was blocked by the permission classifier; the user merged it on GitHub. Built on `feat/dataset-v3`, pushed as draft PR #2.
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
