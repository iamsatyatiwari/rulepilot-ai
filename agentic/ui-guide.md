# UI guide — components and how to use them

The dashboard has five views, selected in the left sidebar:

| View | URL hash | Purpose |
| --- | --- | --- |
| **Start here** (default) | `#guide` | Four-step guided demo with buttons to each page |
| **Investigations** | `#investigations` | Run the Gemini agent on an advisory, read the plain-language summary, approve or reject |
| **Demo bank** | `#bank` | Pay with fictional cards or run attack scenarios; the original rule plus every approved rule decide. Report fraud; investigate customer reports |
| **Rule lab** | `#lab` | A rule and a test transaction side by side; generate matching or near-miss examples; save labelled test cases and run them against any rule |
| **Transaction monitor** (Advanced) | `#monitor` | Batch mock bank feed scored by the engine; approved rules run in shadow mode |
| **Rule engine** (Advanced) | `#engine` | Baseline threshold discovery on the original v1 fixture (M2B) |

Source files: `frontend/src/App.tsx` (shell), `GuideView.tsx`, `InvestigationView.tsx`, `BankView.tsx`, `MonitorView.tsx`, `RuleEngineView.tsx`, `components.tsx` (shared), `api.ts` (typed client), `styles.css`.

---

## 1. Step-by-step: using everything in the UI (about 10 minutes)

**Before you start:** the top bar says **API connected**. On Investigations, the agent chip reads *model · ready*. If it says *not configured*, live runs are disabled, but every step below still works with the recorded runs.

**Step 1: investigate an advisory.**
1. Open **Investigations**.
2. Leave **Test against data** on *Payments scenario v3*.
3. Press **Investigate** on *Preventing Card Testing*. A progress card counts the seconds; a run takes 20–90 s.
4. No key or no quota? Click the *Preventing Card Testing … recorded* chip in **History** instead.

**Step 2: read the result.**
1. The dark **banner** gives the outcome in one sentence.
2. **In plain words** explains, in this order:
   - what the advisory says, and how many quotes were found word-for-word in the source;
   - whether our data can test it;
   - the proposed rule, for example `transactions 1h ≥ 5 AND amount < 5`;
   - how much more fraud it catches on unseen test data, and the cost in false alarms;
   - what you need to decide.
3. For the full audit, open **Evidence and audit trail**. It holds the pipeline, source and quotes, findings, coverage, the candidate table, the held-out test, the agent trace, guardrails, and limitations.

**Step 3: approve.**
1. In **Human review**, type your name and a reason, then press **Approve for further testing**.
2. A green box confirms *Approved by …* and says the rule is now **active**. **Test it in the Demo bank** takes you there. The form disappears; **Record a different decision** brings it back (Reject or Request changes switches the rule off).

**Step 4: see it work in the Demo bank.**
1. Open **Demo bank**. The top panel lists the original rule and every approved rule, each with *try the …* naming the scenario it reacts to.
2. Press the matching scenario:
   - A card-testing rule: **Card-testing attack**. From about the sixth tiny payment the bank shows **Held for review**, with a red line *Blocked by your approved RulePilot rule …*.
   - A SIM-swap rule: **SIM-swap takeover**. The 1,240 transfer is **Held for review**, although the original rule (amount ≥ 1,500) would have approved it.
   - If you run an attack your rules do not cover, a note tells you which scenario they do cover.
3. Press **Why?** on any payment to see the features the engine used.
4. **Normal day** should be all *Approved*. *MegaTech Electronics* at 1,899 is held by the original rule. Tick *Wrong security code* to see an issuer decline.

**Step 5: report fraud (continuous learning).**
1. On a payment the customer did not make, press **Report fraud**. It is stored as a customer-reported fraud case (it also appears in the Rule lab).
2. The **Customer fraud reports** panel shows how many reports the active rules missed. Open **What Gemini will read** to see the summary that code writes from those payments (no names or card numbers).
3. With 3 or more missed reports, press **Investigate reports now** (the scheduled job does the same every few hours). After 20–90 s a note shows the result and how many reported cases the proposed rule catches; review and approve it in **Investigations**.

**Step 6: build your own test data in the Rule lab.**
1. Open **Rule lab** and pick a rule. The left panel shows each condition, what the rule needs, the value in your test transaction, and ✓/✗, plus whether the rule FLAGS or ALLOWS it.
2. Press **Example that matches** or **Near miss** (one condition just fails), or type values yourself.
3. Name it, choose *Fraud* or *Legitimate*, and press **Save as test case**.
4. The **Test cases** table runs every saved case (yours and customer reports) against the selected rule: pass/fail, fraud caught, and false alarms. Switch rules to compare them; **Load** puts a case back into the builder.

**Step 7: the learning loop and honesty.**
1. Investigate the same advisory again: **Covered by existing rules**.
2. Switch **Test against data** to *Sparkov cards v1* and investigate *SIM Swap*: **Not testable with available data**; no rule is invented.

**Step 8 (optional): batch view.** **Advanced → Transaction monitor → Stream 20 transactions**: rows *Caught by approved rule* are fraud only the approved rules stopped.

**Resetting:** **Reset demo** clears bank activity (kept in your browser). Reject an approval to switch its rule off. Delete test cases in the Rule lab.

---

## 2. App shell (`App.tsx`)

| Component | What it shows | How to use |
| --- | --- | --- |
| Sidebar | **Demo**: Start here, Investigations, Demo bank. **Advanced**: Transaction monitor, Rule engine. Platform principles. | Click a page. On phones, open the menu with the ☰ button. |
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

The report opens with the **banner**, the **In plain words** summary (`Summary`), and **Human review**. Every section in the table below except the banner and Human review sits inside the collapsible **Evidence and audit trail**. A **Test against data** picker above the advisory cards chooses `payments-scenario-v3` (the default), `sparkov-cards-v1`, or `card-scenario-v2`.

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

## 4b. Demo bank (`BankView.tsx`)

| Part | What it shows | How to use |
| --- | --- | --- |
| Rules in use | The active rule (decides) and every approved rule (shadow), written as one plain line | Approve rules in Investigations to fill it |
| Demo cards | Asha (everyday), Ben (online shopper), Chen (premium; SIM-swap target) | Click a card to select it |
| Make a payment | Merchant, amount, *Wrong security code*, *Paying from a new device*, **Pay** | Calls `POST /api/v1/bank/payments` with the card's recent activity |
| One-click scenarios | **Card-testing attack**, **SIM-swap takeover**, **Normal day** | Each sends real payments in sequence |
| What the bank decided | Outcome badge (Approved / Held for review / Declined by issuer), a red shadow line when an approved rule would flag, and **Why?** with the derived features | Newest first; **Reset demo** clears it |

The server is stateless. The browser keeps each card's history and security events (SIM change, credential reset, new-device login) and sends them with every payment; timestamps carry the browser's UTC offset so `hour_of_day` is the customer's local hour.

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
| `ruleText` | A rule as one readable line (`transactions 1h ≥ 5 AND amount < 5`) |
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
- Tests: `src/App.test.tsx` (rule engine, `#engine`), `src/InvestigationView.test.tsx` (`#investigations`), `src/MonitorView.test.tsx` (`#monitor`), `src/BankView.test.tsx` (`#bank` and the Start here page). Mock `fetch` by URL suffix. Without a hash the app opens Start here.
