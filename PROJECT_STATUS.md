# RulePilot AI — Project Status

**As of:** 14 Oct 2026 · **Branch:** `feat/m3-intelligence-agent` (not yet merged or pushed) · **Latest commit:** `2f05c23`
**Competition:** Google Cloud AI Builder Cup 2026 — BFSI theme · **Prototype deadline:** 18 Oct 2026 (no time zone published; **team target: submit 17 Oct**)

> **Summary:** The product works end to end on a laptop with live Gemini. A Gemini agent reads a fraud advisory, finds rule-coverage gaps, proposes rules that code measures, and learns from human approvals. **Not done yet:** Cloud Run deployment, merging and pushing to the public repo, the README rewrite, the deck, and the video. All five are required for submission.

---

## 1. Submission checklist (official requirements)

| # | Required deliverable | Status | Blocker / next action |
| --- | --- | --- | --- |
| 1 | Working prototype on Google Cloud (Cloud Run / GCP / Firebase) with a **live URL** | ❌ Not deployed | Need GCP project ID + billing, region, `gcloud` or Cloud Shell, new Gemini key |
| 2 | **Public** GitHub repository with source | ⚠️ Code on local branch only | Merge to `main`, push, confirm repo is public |
| 3 | Demo video, **strictly under 3 minutes** (YouTube / Vimeo / public Drive) | ❌ Not started | Record after deployment; script in section 5 |
| 4 | Presentation deck (PDF): solution architecture + business case | ❌ Not started | Outline in section 5 |
| 5 | Uses Google AI models (Gemini / Gemma) | ✅ Gemini via Google ADK | — |
| 6 | Problem statement identified (BFSI) | ⚠️ Select at submission | Choose "BFSI: Intelligent Risk, Fraud & Financial Experiences" |
| 7 | All materials in English | ✅ | — |

Judging weights: Technical merit & GenAI 40% · Problem alignment & impact 25% · Innovation 25% · UX 10%.

---

## 2. What has been built

### Milestone history

| Milestone | What it delivered | Commit |
| --- | --- | --- |
| M1 Foundation | FastAPI backend, React + TypeScript + Vite frontend, env examples, Windows setup | `f7d2d24` |
| M2A Rule engine | Strict rule schema, deterministic evaluation, metrics, synthetic data, baseline rule, threshold discovery | `f7d2d24` |
| M2B Dashboard | Connected dashboard, backtests, missed-fraud evidence, tests | `c7709a1` |
| M3 Intelligence agent | Gemini + ADK agent, tools, advisories, governance API, investigation UI, local live run, Dockerfile, `agentic/` docs | `00e421c` |
| M4 Continuous learning | Reviewed rule catalog, review-history tool, "covered by existing rules" status, Firestore storage | `2f05c23` |

### Capabilities working today

| Area | Capability | Where |
| --- | --- | --- |
| **Intelligence** | Two curated advisories with source URL, dates, rights note, SHA-256: card testing (testable), FBI IC3 SIM swap (not testable). Analysts can also paste advisory text (≤ 8,000 chars). | `backend/app/intel/` |
| **GenAI agent** | One Google ADK `LlmAgent` (Gemini 3.8 Flash) with 6 bounded tools: rule catalog, review history, training profile, field coverage, candidate evaluation, final submission | `backend/app/agent/` |
| **Safety** | Advisory text treated as untrusted data; no code execution; ≤ 12 model calls, 120 s, ≤ 3 candidates, ≤ 3 conditions; retry and model fallback on 429/503 | `agent.py`, `tools.py` |
| **Verification** | Quotes checked verbatim against the source; coverage recomputed in code; agent claims cross-checked; final status and headline written by code | `orchestrator.py` |
| **Evaluation integrity** | Agent sees training statistics and validation results only; orchestrator runs the held-out test **once** | `tools.py`, `backtest.py` |
| **Rule engine** | Pydantic-validated rules, 6 operators, AND/OR, fail-closed; confusion-matrix metrics; rule-set (OR) comparisons | `backend/app/rules/`, `evaluation.py` |
| **Data** | `synthetic-v1` (120 rows) and `card-scenario-v2` (6,000 rows, ~3% fraud, documented injected card-testing pattern) | `data.py`, `datasets.py` |
| **Governance** | Approve / reject / request changes with reviewer, comment, rule version; approval **never activates**; append-only audit log | `governance.py` |
| **Continuous learning** | Approved rules join the reviewed catalog and are used in every later comparison; agent reads past decisions; returns "covered by existing rules" when nothing new is needed | `governance.py`, `tools.py` |
| **Storage** | Local JSON (development) or Firestore (`RULEPILOT_STORE=firestore`) | `storage.py` |
| **API** | 15 endpoints incl. investigations, review, rule catalog, audit, advisories, agent status | `investigations_api.py`, `api.py` |
| **UI** | Investigations workspace: advisory cards, paste form, rule catalog, history, pipeline, evidence quotes, findings, coverage, candidates, held-out deltas, agent trace, guardrails, review form, limitations. Plus the M2B rule-engine view. | `frontend/src/` |
| **Demo resilience** | 3 recorded real runs (card testing, SIM swap, covered-after-approval) shown when Gemini is unavailable | `backend/app/intel/recorded/` |
| **Deployment prep** | Multi-stage Dockerfile; FastAPI serves API and dashboard on one URL | `Dockerfile` |
| **AI-assistant docs** | `agentic/` (context, guardrails, architecture, skills, tasks, UI guide), `AGENTS.md`, `CLAUDE.md` | `agentic/` |

### Verified results

| Check | Result |
| --- | --- |
| Backend tests | **82 passed** (36 at M2B) |
| Frontend tests | **10 passed** (5 at M2B); type check and production build pass |
| Dependency check / secret scan | Clean |
| Live run — card testing | Gap found; 3 candidates checked on validation; held-out rule-set recall **+51.3 pp**, false-positive rate +0.52 pp; 5/5 quotes verified |
| Live run — SIM swap | **Not testable** (missing `sim_swap_event`, `device_id`, `sms_2fa_reset`); no rule invented; held-out test not used |
| Live learning loop | Run 1 proposed rule (+41.0 pp recall) → approved → run 2 compared against 2 rules with 1 prior review → **covered by existing rules** |
| HTTP flow | Investigation → review → catalog → audit verified over the API |

All metrics come from synthetic data and are not real-world detection rates.

---

## 3. What is left

### Must do before submission (in order)

| # | Task | Owner | Effort | Depends on |
| --- | --- | --- | --- | --- |
| 1 | Rotate the Gemini key (the current one was shared in chat); enable billing on its project | User | 10 min | — |
| 2 | Provide GCP project ID, region (suggest `asia-southeast1`), `gcloud` or Cloud Shell | User | 15 min | — |
| 3 | **Deploy to Cloud Run**: Secret Manager, Firestore database, `RULEPILOT_STORE=firestore`, deploy, smoke test, one live investigation | Claude + user | 1–2 h | 1, 2 |
| 4 | **Rewrite `README.md`**. It still describes M2B and says the app calls no AI service. Needs: live URL, architecture, how to run, limitations | Claude | 1 h | 3 for URL |
| 5 | Merge `feat/m3-intelligence-agent` → `main`, push, make repo **public** | User | 10 min | 4 |
| 6 | **PDF deck**: problem, solution, architecture diagram, agent and guardrails, learning loop, results, limitations, roadmap, business case | Team (Claude drafts) | 3–4 h | 3 |
| 7 | **Video under 3 minutes** on the deployed URL | Team | 2 h | 3, 6 |
| 8 | Submit on Hack2skill; select BFSI theme; double-check links open logged-out | Team | 30 min | all |

### Should do if time allows

| Task | Why |
| --- | --- |
| Golden-set evaluation script (L4): re-run advisories and check expected outcomes | Strengthens the 40% technical-merit score |
| Replace the J.P. Morgan excerpt with a public-domain card-testing source | Removes the third-party-IP risk |
| Increase font sizes in the older rule-engine view (8–10 px) | Readability in the video (UX 10%) |
| Basic access control on review endpoints for the public URL | Prevents strangers editing the demo catalog |
| Confirm the official launch date and submission time zone with the organizer (Discord / Hack2skill) | "Fresh code" rule; deadline certainty |

### Deferred (roadmap slide, not before 18 Oct)

Scheduled ingestion (Cloud Scheduler + Cloud Run Job) · re-backtesting approved rules on new data (drift) · real transaction data · authentication and reviewer identity · rule activation workflow · AML, account takeover, and scam typologies.

---

## 4. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| No live URL by deadline | **Disqualifying** | Deploy first (task 3); Dockerfile ready |
| Gemini capacity (503) and free-tier quota (429) during judging | Live run fails | Model fallback chain; billing; recorded runs always viewable |
| Cloud Run restarts lose state | Approvals disappear | Firestore storage (task 3) |
| Third-party text (J.P. Morgan excerpt, ~110 words) | Rules forbid third-party IP | Short attributed excerpts; replace if a public-domain source is found |
| Synthetic data perceived as circular | Credibility | Disclosed everywhere; SIM-swap "not testable" shows honesty; real data on roadmap |
| Public demo has no authentication | Visitors can approve or reject | Acceptable for prototype; add a shared reviewer passcode if time permits |
| API key exposed in chat transcript | Misuse | Rotate (task 1); new key only in Secret Manager |

---

## 5. Submission material outlines

**Video (≤ 2:50):**
1. **0:00–0:20 Problem.** Fraud techniques change faster than rules.
2. **0:20–1:20 Live investigation of card testing.** Show source quotes verified, coverage gap with missing fields, three candidates, and the held-out result.
3. **1:20–1:45 Approve.** The rule enters the catalog, not activated.
4. **1:45–2:10 Re-run.** "Covered by existing rules": the learning loop.
5. **2:10–2:30 SIM swap.** Not testable; nothing invented.
6. **2:30–2:50 Architecture and guardrails.**

**Deck:**
1. Problem and why it matters
2. Workflow
3. Architecture (Cloud Run, Gemini, ADK, Firestore)
4. Agent, tools, and guardrails
5. Evaluation integrity
6. Continuous learning
7. Results, with the synthetic caveat
8. Business case: analyst time to turn intelligence into a tested rule
9. Limitations
10. Roadmap

---

## 6. Where to find things

| Need | File |
| --- | --- |
| Full implementation log | [IMPLEMENTATION_SUMMARY.txt](IMPLEMENTATION_SUMMARY.txt) |
| Project context, decisions | [agentic/context.md](agentic/context.md) |
| Architecture, API, configuration | [agentic/architecture.md](agentic/architecture.md) |
| How to run, test, deploy, demo | [agentic/skills.md](agentic/skills.md) |
| UI components and demo script | [agentic/ui-guide.md](agentic/ui-guide.md) |
| Task tracker | [agentic/tasks.md](agentic/tasks.md) |
| Non-negotiable rules | [agentic/guardrails.md](agentic/guardrails.md) |
