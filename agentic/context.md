# Project context

## Product

**RulePilot AI — Continuous Financial Rule Intelligence.**

Fraud techniques change faster than detection rules. RulePilot turns new financial-crime intelligence into tested, governed rule proposals:

```
advisory → structured findings → coverage-gap check → candidate rules
        → validation metrics → single held-out test → human review → audit
```

- **Gemini proposes and coordinates.** One Google ADK agent reads the advisory and uses bounded tools.
- **The deterministic engine measures.** Python code validates rules and computes all metrics.
- **Humans decide.** Only a human approval activates a rule; reject or request-changes switches it off. Every step is audited.

First vertical slice: payment-card fraud. Account takeover, scams, and AML are future extensions.

## Competition (verified 2026-10-14 from aibuildercup.com)

| Item | Requirement |
| --- | --- |
| Event | Google Cloud AI Builder Cup 2026, theme "BFSI: Intelligent Risk, Fraud & Financial Experiences" |
| Prototype deadline | Oct 18, 2026 (no time zone published — team targets Oct 17) |
| Mandatory deliverables | Live URL on Cloud Run/GCP/Firebase; video **under 3 minutes**; **public** GitHub repo; PDF deck (architecture + business case) |
| Model rule | Must use Google AI models (Gemini/Gemma) |
| Judging | Technical merit & GenAI 40%, problem alignment & impact 25%, innovation 25%, UX 10% |
| Other rules | Fresh code only; no third-party IP without permission; English |
| Dates | Shortlist Nov 7; Grand Finale Dec 4, Singapore |
| Team | 2 developers |

## Current status

| Milestone | State |
| --- | --- |
| M1 foundation, M2A rule engine, M2B dashboard | Done, committed |
| M3 T0–T7 agent, tools, advisories, governance API, investigation UI, local live E2E | Done |
| M3 T8 Cloud Run deployment | Dockerfile ready; needs GCP project |
| M4 continuous learning: reviewed rule catalog, review-history tool, Firestore storage | Done (L1–L3), verified live |
| T9 README, deck, 3-minute video | README rewritten (15 Oct); deck and video not started |
| Shadow scoring (mock bank feed) and scheduled ingestion endpoint | Done locally, not yet deployed |
| `payments-scenario-v3` dataset (30k rows, 12 fields) and golden-set evaluation (L4) | Done locally; live golden run passes on v3 |
| `sparkov-cards-v1` (75k rows from the independent MIT-licensed Sparkov simulator) | Done locally |
| Demo bank, Start here guide, simplified investigations UI | Done locally |
| Approval activates rules (16 Oct team decision); Rule lab; customer fraud reports feeding the scheduled job | Done locally |

Latest verification: 133 backend tests, 21 frontend tests, type check and build passing; production-mode and Firestore-emulator smoke checks pass. Live learning loop verified: run → approve → re-run returns `covered_by_existing_rules`.

## Key decisions (do not reverse without a demonstrated need)

1. **Own lightweight rule engine**, not an external rule engine.
2. **One ADK agent** with five tools. No multi-agent system.
3. **Gemini API key auth** (`GOOGLE_API_KEY`); Secret Manager on Cloud Run. Vertex AI with ADC is supported by config but not used.
4. **Model fallback chain** because Gemini Flash capacity is unreliable: `gemini-3.8-flash → gemini-flash-latest → gemini-3.6-flash → gemini-3.5-flash-lite`.
5. **Synthetic data, honestly labelled.** `card-scenario-v2` contains an injected card-testing pattern; `payments-scenario-v3` (default for investigations) adds an injected SIM-swap account-takeover pattern and device, SIM-change, credential-reset, and payee fields. Always say so. `sparkov-cards-v1` comes from an independent simulator (not designed by us) and has no SIM, device, or decline fields.
6. **Two demo advisories:** card testing (testable) and SIM swap — testable on `payments-scenario-v3`, `not_testable` on `card-scenario-v2` (shows the system refuses to invent a link when the data is missing).
7. **Single Cloud Run service** serving API + built dashboard on one origin.
8. **"Learning" means governed system state, not model training:** approved rules enter the catalog and reviewer feedback is available to the agent as data. No fine-tuning, no autonomous rule changes.

## Known risks

- J.P. Morgan advisory text is copyrighted; only ~110 words of attributed excerpts are stored. Replace with a public-domain source if one is found.
- Gemini free-tier quotas produce 429s; enable billing for the demo.
- Cloud Run filesystem is ephemeral; set `RULEPILOT_STORE=firestore` in deployment or approvals are lost on restart.
- No authentication; reviewer names are self-declared.
- The pre-competition fresh-code rule: commits are dated from Oct 12, 2026.

## Glossary

| Term | Meaning |
| --- | --- |
| Baseline | `RP-BASELINE-001`, flag amount ≥ 1,500 |
| Rule set / combined | Baseline OR candidate — what the institution would run if the candidate were added |
| Coverage | Whether fields needed by an advisory exist in the dataset: testable, partially testable, not testable |
| Held-out test | Test split, evaluated once per investigation by the orchestrator |
| Reviewed rule catalog | Active baseline + human-approved (inactive) rules; every new investigation is compared against all of them |
| Recorded run | A real past live run saved under `backend/app/intel/recorded/` and shown with a "Recorded run" badge |
