# RulePilot AI — Project Status

**As of:** 15 Oct 2026 · **Main:** PR #1 merged; PR #2 (dataset v3 + golden set) and the README/status PR awaiting merge
**Competition:** Google Cloud AI Builder Cup 2026 — BFSI theme · **Prototype deadline:** 18 Oct 2026 (no time zone published; **team target: submit 17 Oct**)

> **Summary:** The product works end to end locally with live Gemini.
> - Built and verified: governed learning, shadow scoring on a mock bank feed, scheduled ingestion, a 30,000-row dataset where both demo advisories are testable, and a golden-set evaluation.
> - **Deployed 18 Oct:** https://rulepilot-ai-876092777486.asia-southeast1.run.app (Cloud Run, Vertex AI Gemini, Firestore). Smoke check 24/24; live investigations pass. Still missing: the **PDF deck** and the **video**.

---

## 1. Submission checklist (official requirements)

| # | Required deliverable | Status | Blocker / next action |
| --- | --- | --- | --- |
| 1 | Working prototype on Google Cloud (Cloud Run / GCP / Firebase) with a **live URL** | ✅ Deployed 18 Oct | https://rulepilot-ai-876092777486.asia-southeast1.run.app |
| 2 | **Public** GitHub repository with source | ✅ Public; `main` updated | Merge PR #2 and the README PR |
| 3 | Demo video, **strictly under 3 minutes** (YouTube / Vimeo / public Drive) | ❌ Not started | Record after deployment; script in section 5 |
| 4 | Presentation deck (PDF): solution architecture + business case | ❌ Not started | Outline in section 5 |
| 5 | Uses Google AI models (Gemini / Gemma) | ✅ Gemini via Google ADK | — |
| 6 | Problem statement identified (BFSI) | ⚠️ Select at submission | Choose "BFSI: Intelligent Risk, Fraud & Financial Experiences" |
| 7 | All materials in English | ✅ | — |
| — | README describing the current product | ✅ Rewritten 15 Oct; live URL added 18 Oct | — |

Judging weights: Technical merit & GenAI 40% · Problem alignment & impact 25% · Innovation 25% · UX 10%.

---

## 2. What has been built

### Milestone history

| Milestone | What it delivered | Commit |
| --- | --- | --- |
| M1 Foundation | FastAPI backend, React + TypeScript + Vite frontend | `f7d2d24` |
| M2A/M2B Rule engine + dashboard | Strict rule schema, deterministic evaluation, metrics, threshold discovery, backtests, dashboard | `f7d2d24`, `c7709a1` |
| M3 Intelligence agent | Gemini + ADK agent, tools, advisories, governance API, investigations UI, Dockerfile | `00e421c` |
| M4 Continuous learning | Reviewed rule catalog, review-history tool, "covered by existing rules", Firestore storage | `2f05c23` |
| Shadow scoring + ingestion (PR #1) | Mock bank feed, `/transactions/score` and `/transactions/simulate`, Transaction monitor, `/ingestion/run` for Cloud Scheduler, per-request model timeout | `7623795`, `a7016c4` |
| Sparkov data, demo bank, simpler UI | `sparkov-cards-v1`, Demo bank page and API, Start here guide, summary-first investigations | `49f301b`, `18f41c1` |
| Dataset v3 + golden set (PR #2) | `payments-scenario-v3`, 5 new fields, SIM-swap takeover pattern, golden-set evaluation, recorded runs refreshed on v3 | `fcd378d`, `28d3ea5` |

### Capabilities working today

| Area | Capability |
| --- | --- |
| **Intelligence** | Curated advisories: card testing, and the FBI IC3 SIM-swap PSA. Each has source URL, dates, rights note and SHA-256. Analysts can also paste advisory text (≤ 8,000 chars). |
| **GenAI agent** | One Google ADK `LlmAgent` with 6 bounded tools. Retry and model fallback on 429/503; HTTP timeout on every request. |
| **Verification** | Quotes are verified verbatim. Coverage is recomputed in code and the agent's claims are cross-checked. The status and headline are written by code. |
| **Evaluation integrity** | The agent sees training statistics and validation results only. The held-out test runs once, triggered by the orchestrator. |
| **Data** | `synthetic-v1` (120 rows); `card-scenario-v2` (6,000 rows, 7 fields); `payments-scenario-v3` (30,000 rows, 12 fields, 3 fraud modes, 202 held-out fraud records; default dataset). |
| **Governance** | Approve / reject / request changes. Approval never activates a rule. Append-only audit log. Local JSON or Firestore storage. |
| **Continuous learning** | Approved rules join the reference rule set and the agent reads earlier review decisions. A run can end "covered by existing rules". |
| **Shadow scoring** | The mock bank feed (~40% fraud, for demo purposes) is scored by active rules; approved rules run in shadow and never change the decision. |
| **Scheduled ingestion** | Token-protected `/ingestion/run`. At most one new or changed advisory per call. |
| **Golden set** | 4 cases (advisory × dataset): `app/golden.py`, `scripts/golden_eval.py`. The recorded runs pass their cases offline. |
| **UI** | Start here guide, Investigations (summary first, audit folded), **Demo bank** (fictional cards, attack scenarios, shadow verdicts), Transaction monitor, Rule engine. |
| **Demo resilience** | 4 recorded real runs are shown when Gemini is unavailable. |

### Verified results (latest)

| Check | Result |
| --- | --- |
| Backend tests | **123 passed**, with no Gemini calls |
| Frontend tests | **18 passed**; type check and production build pass |
| Production-mode smoke check | **29/29** (`scripts/smoke_check.py --review`) |
| Firestore emulator, Docker build, headless Chrome | Pass (14 Oct) |
| Live golden set on v3 | `card-testing-payments-v3` and `sim-swap-payments-v3` **PASS** |
| Live run: card testing (v3) | Pending review. Rule: 1h velocity ≥ 5 AND amount < 5. Held-out recall **+5.4 pp**, FPR +0.21 pp. 4/4 quotes verified. |
| Live run: SIM swap (v3) | **Testable**, pending review. Rule: SIM changed ≤ 1 day ago. Held-out recall **+10.8 pp**, FPR +0.83 pp. 3/3 quotes verified. |
| Live run: SIM swap (v2) | **Not testable** (no SIM/device fields). No rule invented; held-out test not used. |
| Live learning loop (v3) | Approve card-testing rule → re-run compares against 2 rules and 1 prior review → **covered by existing rules** |

All metrics come from synthetic data and are not real-world detection rates. Every live run on 14–15 Oct used the `gemini-3.5-flash-lite` fallback, because the stronger models returned 429/503 on the free tier.

---

## 3. What is left

### Must do before submission (in order)

| # | Task | Owner | Effort | Depends on |
| --- | --- | --- | --- | --- |
| 1 | Merge the Sparkov / demo bank / UI PR | User | 5 min | — |
| 2 | Rotate the Gemini key (it was shared in chat); **enable billing** on its project | User | 10 min | — |
| 3 | Provide a GCP project ID with billing and a region (suggest `asia-southeast1`). Install `gcloud` (`brew install --cask google-cloud-sdk`) or use Cloud Shell. | User | 15 min | — |
| 4 | **Deploy to Cloud Run**: Secret Manager, Firestore, deploy, smoke test, one live investigation, Cloud Scheduler job | Claude + user | 1–2 h | 2, 3 |
| 5 | Add the live URL to the README | Claude | 5 min | 4 |
| 6 | **PDF deck**: problem, workflow, architecture, agent and guardrails, evaluation integrity, learning loop, shadow scoring, results, business case, limitations, roadmap | Team (Claude drafts) | 3–4 h | 4 |
| 7 | **Video under 3 minutes** on the deployed URL | Team | 2 h | 4, 6 |
| 8 | Submit on Hack2skill; select the BFSI theme; check that every link opens logged out | Team | 30 min | all |

### Should do if time allows

| Task | Why |
| --- | --- |
| Replace the J.P. Morgan excerpt with a public-domain card-testing source | Removes the third-party-IP risk |
| Shared reviewer passcode on review endpoints | Stops visitors to the public URL from changing the demo catalog |
| Larger fonts in the older rule-engine view (8–10 px) | Readability in the video (UX 10%) |
| Two-condition built-in threshold discovery | Today only the agent proposes combined rules |
| Confirm the submission time zone with the organizer | Deadline certainty |

### Deferred (roadmap slide)

Re-backtesting approved rules on new data (drift) · real transaction data · authentication and reviewer identity · rule activation workflow · AML and scam typologies.

---

## 4. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| No live URL by the deadline | **Disqualifying** | Deploy first (task 4); Dockerfile and smoke check are ready |
| Gemini free-tier quota (429) and capacity (503) during judging | Live run fails or uses the weakest model | Enable billing; the fallback chain and recorded runs are always available |
| Cloud Run restarts lose state | Approvals disappear | `RULEPILOT_STORE=firestore` |
| Third-party text (J.P. Morgan excerpt, ~110 words) | Rules forbid third-party IP | Short attributed excerpts; replace if possible |
| Synthetic data seen as circular | Credibility | Injected patterns disclosed; SIM swap "not testable" on v2 shows honesty |
| Public demo has no authentication | Visitors can approve or reject | Acceptable for a prototype; add a passcode if time permits |
| API key exposed in a chat transcript | Misuse | Rotate it (task 2); keep the new key only in Secret Manager |

---

## 5. Submission material outlines

**Video (≤ 2:50):**
1. **0:00–0:20 Problem.** Fraud techniques change faster than rules.
2. **0:20–1:10 Live card-testing investigation.** Verified quotes, coverage gap, three candidates, held-out result.
3. **1:10–1:30 Approve.** The rule enters the catalog but is not activated.
4. **1:30–1:50 Re-run.** "Covered by existing rules": the learning loop.
5. **1:50–2:15 SIM swap.** Testable on v3 with a new rule; not testable on v2, where nothing is invented.
6. **2:15–2:35 Transaction monitor.** The approved rule catches fraud in shadow mode without changing decisions.
7. **2:35–2:50 Architecture and guardrails.**

**Deck:** problem · workflow · architecture (Cloud Run, Gemini, ADK, Firestore, Scheduler) · agent, tools and guardrails · evaluation integrity and golden set · continuous learning · shadow scoring · results (with the synthetic caveat) · business case (analyst time from advisory to tested rule) · limitations · roadmap.

---

## 6. Where to find things

| Need | File |
| --- | --- |
| Product overview, run and deploy | [README.md](README.md) |
| Full implementation log | [IMPLEMENTATION_SUMMARY.txt](IMPLEMENTATION_SUMMARY.txt) |
| Project context, decisions | [agentic/context.md](agentic/context.md) |
| Architecture, API, configuration | [agentic/architecture.md](agentic/architecture.md) |
| How to run, test, deploy, demo | [agentic/skills.md](agentic/skills.md) |
| UI components and demo script | [agentic/ui-guide.md](agentic/ui-guide.md) |
| Task tracker | [agentic/tasks.md](agentic/tasks.md) |
| Non-negotiable rules | [agentic/guardrails.md](agentic/guardrails.md) |
| In-flight work and handoff | [agentic/session-log.md](agentic/session-log.md) |
