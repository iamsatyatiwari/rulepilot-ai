# UI guide — components and how to use them

The dashboard has three views, selected in the left sidebar:

| View | URL hash | Purpose |
| --- | --- | --- |
| **Investigations** (default) | `#investigations` | Run the Gemini agent on an advisory and review the result |
| **Transaction monitor** | `#monitor` | Mock bank feed scored by the engine; approved rules run in shadow mode |
| **Rule engine** | `#engine` | Baseline threshold discovery on the original v1 fixture (M2B) |

Source files: `frontend/src/App.tsx` (shell), `InvestigationView.tsx`, `MonitorView.tsx`, `RuleEngineView.tsx`, `components.tsx` (shared), `api.ts` (typed client), `styles.css`.

---

## 1. Quick start: a 2-minute demo

1. Open the dashboard. The top bar should say **API connected** and the agent chip **gemini-3.8-flash · ready**.
2. Under **Curated advisories**, click **Investigate** on *Preventing Card Testing*. Wait 20–90 s.
3. Read the dark **result banner**: it states the measured held-out change.
4. Walk down the report: **Pipeline → Source & quotes → Findings → Coverage → Candidates → Held-out test → Agent trace → Guardrails**.
5. In **Human review**, enter your name and a comment, then click **Approve for further testing**. The decision appears in the review history with *activation: not activated*.
6. Click **Investigate** on the *SIM Swap* advisory. The banner reports **Not testable with available data** and no rule is proposed — the system does not invent a link.
7. Use the **History** strip to switch between runs.
8. **Learning loop:** after approving in step 5, the **Reviewed rule catalog** lists the rule as *Approved · not active*. Investigate the card-testing advisory again: the banner reports **Covered by existing rules** because the approved rule is now part of the rule set.

9. **Shadow scoring:** open **Transaction monitor** and click **Stream 20 transactions**. Rows marked *Caught only by approved rule* are synthetic fraud the baseline allowed but the approved rule would flag. The decision never changes, because approval does not activate a rule.

If Gemini is busy or not configured, open the **recorded** runs in History; they are real earlier runs.

---

## 2. App shell (`App.tsx`)

| Component | What it shows | How to use |
| --- | --- | --- |
| Sidebar | Brand, workspace, navigation, platform principles | Click **Investigations** or **Rule engine**. On phones, open with the ☰ button. |
| Top bar breadcrumb | Current view | — |
| API status pill | `Checking API` / `API connected` / `API unavailable` from `GET /health` | If unavailable, start the backend (see `skills.md` skill 1). |
| Footer | Synthetic-data disclaimer | — |

---

## 3. Investigations view (`InvestigationView.tsx`)

### 3.1 Header

| Element | Meaning |
| --- | --- |
| Agent chip | Model name and whether the server has Gemini credentials (`GET /api/v1/agent/status`). Green = ready, amber = not configured. |
| **Refresh** | Reloads agent status, advisories, and history. |

### 3.2 Step 1 — Choose intelligence

**Advisory cards** — one per curated source (`GET /api/v1/advisories`).

| Part | Meaning |
| --- | --- |
| Source-type tag | Government PSA, industry guidance, regulatory advisory, or analyst supplied |
| Title, publisher, date | Source metadata |
| Excerpt | First 210 characters of the stored text |
| **Source ↗** | Opens the original page |
| **Investigate →** | Starts a live run (`POST /api/v1/investigations`). Disabled when the agent is not configured or a run is in progress. |

**Paste an advisory** — toggles a form for your own intelligence text.

| Field | Rule |
| --- | --- |
| Title, Publisher | Required, ≤ 200 characters |
| Source URL | Required, must be `http(s)://` |
| Advisory text | 50–8,000 characters; a live counter is shown |

The pasted text is treated as untrusted data. Instructions hidden inside it are ignored by design.

**Running card** — appears during a run with elapsed seconds. Runs can take up to ~2 minutes when the service falls back between models.

**Errors** — shown in a red inline box, e.g. "An investigation is already running" (429) or "The Gemini agent is not configured" (503).

### 3.3 Reviewed rule catalog (learning loop)

Lists the rules every new investigation is compared against (`GET /api/v1/rule-catalog`):

| Badge | Meaning |
| --- | --- |
| *Active baseline* | `RP-BASELINE-001`, the only active rule |
| *Approved · not active* | A candidate a human approved; shows conditions, approver, time, source advisory, and the review comment |

Approving a candidate adds it here; a later reject or request-changes removes it. The agent also receives recent review decisions through its `get_review_history` tool, so reviewer tolerances (e.g. "keep FPR under 1%") inform future proposals.

### 3.4 History strip

Buttons for the 8 most recent investigations. The coloured dot is the status (amber = pending review, blue = not testable, grey = insufficient evidence, red = agent incomplete). `recorded` marks saved demo runs. Click to open. Green dot = covered by existing rules.

### 3.5 Report

| Section | What it shows | How to read it |
| --- | --- | --- |
| **Result banner** | Status pill, deterministic headline, advisory, dataset version, seed, number of reviewed rules compared against, prior reviews available, Live/Recorded badge, time, model, model-call count | The headline is written by code, not by the model. Statuses: pending human review, covered by existing rules, not testable, insufficient evidence, agent incomplete. |
| **Pipeline** | Six steps: Source, Findings, Coverage, Candidates, Held-out test, Human review | Green = done, grey = skipped, red = failed, amber = waiting for you. |
| **Intelligence source** | URL, published and retrieved dates, SHA-256 of the stored text | The hash ties the result to the exact text the agent read. |
| **Evidence quotes** | Quotes the agent cited | ✅ *Verified in source* = found verbatim by code. ⚠ *Not found in source* = the model paraphrased or invented it; treat the finding with caution. |
| **Structured findings** | Technique, summary, behaviors, indicators, testable hypotheses, uncertainties | Extracted by Gemini; reviewers should read the uncertainties. |
| **Coverage-gap analysis** | Status badge; chips for required & available (green), required but missing (red), fields the existing rule checks (grey); agent assessment | Status is computed by code from the field lists. |
| **Candidate rules · validation** | Each candidate's conditions; candidate recall; rule-set recall, false-positive rate (FPR), and alerts as *baseline → baseline + candidate* | **Selected** marks the agent's choice. All numbers are from the validation split. |
| **Held-out test** | Delta strip (recall, precision, FPR, additional fraud detected, alert volume) and two metric columns: existing reviewed rule set vs existing set + candidate | Evaluated once by the orchestrator on records the agent never saw. Green = favourable, red = cost. |
| **Agent trace** | Every tool call in order with a one-line summary; model calls, tokens, time limit | Red step numbers are tool calls the engine rejected (e.g. unavailable field). A grey note means the run fell back to another model. |
| **Guardrails** | Deterministic checks with ✔/✘ and detail | Any ✘ should be discussed in review. |
| **Human review** | Review history and decision form | See below. |
| **Limitations** | Dataset, intelligence, and sample-size caveats plus the agent's own | Mention these when presenting. |

### 3.6 Human review panel

1. Enter **Reviewer** (≤ 100 chars) and **Comment** (≤ 1,000 chars). Both are required.
2. Choose **Approve for further testing**, **Request changes**, or **Reject**.
3. The decision is stored with rule ID, rule version and timestamp (`POST /api/v1/investigations/{id}/review`) and added to the audit log.
4. Approval **never activates** the rule; history shows *activation: not activated*.

The form appears only when the status is *Pending human review*. Multiple decisions are kept in order.

---

## 4a. Transaction monitor (`MonitorView.tsx`)

| Element | Meaning |
| --- | --- |
| Shadow chip | Number of approved (inactive) rules running in shadow |
| **Stream 20 transactions** | `POST /api/v1/transactions/simulate` with the next seed; rows appear one by one |
| Rules panel | *Active · decides* (baseline) and *Shadow · approved* rules with provenance |
| Summary strip | Fraud caught by active rules, **caught only by approved rules** (highlighted), missed by all, shadow false alarms |
| Feed table | Features, active *Decision*, *Shadow* verdict, synthetic label, and outcome tag. Green rows = caught only in shadow; red rows = missed by every rule |
| Score a transaction | Presets (*Card-testing burst*, *SIM-swap takeover*, *Large purchase abroad*, *Everyday purchase*) or manual values → `POST /api/v1/transactions/score` |

The result banner in Investigations now shows the latest human decision (e.g. *Rejected*) instead of *Pending human review* once a review exists.

## 4. Rule engine view (`RuleEngineView.tsx`)

Baseline reference from M2A/M2B on the 120-row `synthetic-v1` fixture.

| Component | How to use |
| --- | --- |
| Overview cards | API, dataset size, discovered candidate |
| **Run backtest** | Compares the baseline with the discovered threshold candidate on the test split |
| Metric columns + trade-off card | Precision, recall, FPR, confusion matrix, alert change |
| Candidate proposal | Exact condition, rationale, validation evidence |
| Review status | Explains that review decisions are recorded on investigations |
| Missed fraud table | Test-split fraud IDs missed by each rule; no feature values shown |

---

## 5. Shared components (`components.tsx`)

| Export | Purpose |
| --- | --- |
| `MetricColumn` | Alerts, precision, recall, FPR, confusion matrix, evaluated count for one rule or rule set |
| `CandidateConditions` | AND/OR and each `field operator value` row |
| `formatPercent`, `formatDelta`, `formatCount` | Safe formatting; missing values render as `—`, never `NaN` |
| `safeMessage` | Maps API errors to user-safe text |

---

## 6. States and accessibility

- Every async area has loading, error (with retry), and empty states.
- Status changes use `role="status"`/`aria-live`; errors use `role="alert"`.
- Tables have captions; buttons have accessible names (e.g. "Investigate Preventing Card Testing…").
- Layout adapts at 1120 px, 820 px (sidebar becomes a drawer), and 560 px.

## 7. For developers

- Add API types to `api.ts` first; components consume only typed responses.
- Long-running calls pass `INVESTIGATION_TIMEOUT_MS` (180 s); everything else uses 10 s.
- Tests: `src/App.test.tsx` (rule engine, uses `#engine`) and `src/InvestigationView.test.tsx` (investigation flow). Mock `fetch` by URL suffix.
