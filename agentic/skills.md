# Skills — repeatable procedures

Each skill lists when to use it, the steps, and how to verify. Commands are Windows PowerShell from the repository root unless stated. Always respect [guardrails.md](guardrails.md).

---

## 1. Set up and run locally

**When:** first checkout, or after dependency changes.

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
copy .env.example .env          # set GOOGLE_API_KEY in backend\.env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Second window:

```powershell
cd frontend
npm ci
npm run dev
```

**Verify:** `http://127.0.0.1:8000/health` returns `{"status":"ok"}`; `http://localhost:5173` shows the agent chip as "ready".

## 2. Run every check before committing

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend; npm test; npx tsc -b --pretty false; npm run build
cd ..; git diff --check
```

**Verify:** all pass. Expected warning: one Starlette TestClient deprecation.

## 3. Run a live investigation without the UI

```powershell
cd backend
$body = '{"advisory_id":"jpm-card-testing"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/investigations -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 200
```

Expect 20–90 s. `status` should be `pending_human_review` for card testing and `not_testable` for `fbi-ic3-sim-swap-2022`. If you see `agent_incomplete`, read `report.model_run.errors` (see skill 10).

## 4. Add a curated advisory

1. Confirm we may quote it (public domain, or short attributed excerpt).
2. Create `backend/app/intel/advisories/<advisory-id>.json` with: `advisory_id` (lowercase, hyphens), `title`, `publisher`, `source_url`, `published_date` (or null), `retrieved_at`, `source_type` (`government_psa` | `regulatory_advisory` | `industry_guidance`), `rights_note`, `excerpt` (verbatim text, ≤ 20,000 chars).
3. Update the expected id set in `tests/test_investigations.py::test_advisories_and_agent_status_do_not_expose_secrets`.
4. Run skill 2, then skill 3 with the new id.

## 5. Add an agent tool

1. Add a method on `InvestigationToolkit` in `app/agent/tools.py` with type hints and a docstring with `Args:` (ADK builds the function declaration from them).
2. Validate and bound every input; return `{"ok": False, "error": ...}` on bad input; call `self._record(...)`.
3. It must not read `context._test` or touch network/files.
4. Add it to `agent_tools()`; mention when to use it in `INSTRUCTION` in `app/agent/agent.py`.
5. Add a summary branch in `_summarize_result` in `orchestrator.py`.
6. Tests in `tests/test_agent_tools.py`: JSON-serializable output, invalid input, bounds.

## 6. Add a transaction field or dataset

1. Add an optional field to `Transaction` with `description=` and `json_schema_extra={"rule_eligible": True}`.
2. Populate it in the generator in `app/data.py` (older datasets leave it `None`; rules fail closed).
3. For a new dataset, register it in `app/datasets.py` (`DatasetInfo` with version, seed, limitations) and add its id to the `Literal` types in `api.py` and `investigations_api.py`.
4. Document injected patterns in `limitations`.
5. Keep older generators byte-identical (draw new fields after the shared row) so recorded runs stay reproducible.
6. Judge the data design on training/validation splits only, then run the golden set (skill 7).

## 7. Change the prompt or model

1. Edit `INSTRUCTION` in `app/agent/agent.py` or `RULEPILOT_GEMINI_MODEL`.
2. Run the golden set: `cd backend && .venv/bin/python scripts/golden_eval.py` (add `--repeat 3` for stability, `--case <id>` to limit, `--save DIR` to keep reports). Every case must PASS: expected status and coverage, all guardrails, verified quotes, relevant rule fields. Cases live in `app/golden.py`.
3. Never judge prompt changes by held-out test numbers.

## 8. Refresh the recorded demo runs

1. Run both advisories live (skill 3) and check results in the UI.
2. Copy the stored reports from `backend/.rulepilot_data/investigations/<id>.json`. Save only the `report` object to `backend/app/intel/recorded/<name>.json`.
3. Confirm no secrets: `Select-String -Path backend\app\intel\recorded\*.json -Pattern 'GOOGLE_API_KEY|AQ\.|AIza'` returns nothing.

## 9. Deploy to Cloud Run

Prerequisites: GCP project with billing, `gcloud` (or Cloud Shell), a Gemini API key.

```bash
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com
gcloud firestore databases create --location=asia-southeast1
printf '%s' 'NEW_GEMINI_KEY' | gcloud secrets create gemini-api-key --data-file=-
gcloud run deploy rulepilot-ai --source . --region asia-southeast1 \
  --allow-unauthenticated --memory 1Gi --cpu 1 --timeout 300 \
  --max-instances 2 --concurrency 10 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=FALSE,RULEPILOT_STORE=firestore,GOOGLE_CLOUD_PROJECT=PROJECT_ID \
  --set-secrets GOOGLE_API_KEY=gemini-api-key:latest
```

Grant the runtime service account `roles/secretmanager.secretAccessor` on the secret and `roles/datastore.user` on the project if deploy or the first review reports access denied.

**Scheduled ingestion (the cron job):**

```bash
TOKEN=$(openssl rand -hex 24)
printf '%s' "$TOKEN" | gcloud secrets create ingest-token --data-file=-
gcloud run services update rulepilot-ai --region asia-southeast1 \
  --update-secrets RULEPILOT_INGEST_TOKEN=ingest-token:latest
gcloud services enable cloudscheduler.googleapis.com
gcloud scheduler jobs create http rulepilot-ingest --location asia-southeast1 \
  --schedule "0 */6 * * *" --http-method POST \
  --uri "https://SERVICE_URL/api/v1/ingestion/run" \
  --headers "X-RulePilot-Ingest-Token=$TOKEN" --attempt-deadline 300s
gcloud scheduler jobs run rulepilot-ingest --location asia-southeast1   # trigger once now
```

**Verify:** `/health`, `/api/v1/agent/status` shows `configured: true`, the dashboard loads at `/`, one live investigation completes, `backend/scripts/smoke_check.py https://SERVICE_URL` passes (without `--review` on the demo deployment), and the scheduler run appears in History as *scheduled*.

## 10. Demonstrate the learning loop

1. Investigate *Preventing Card Testing* → status *Pending human review*.
2. Approve it with a comment (e.g. "Keep rule-set FPR under 1%"). The **Reviewed rule catalog** now lists the rule as *Approved · not active*.
3. Investigate the same advisory again. Expect the banner *Covered by existing rules*, "compared against 2 reviewed rule(s) · 1 prior review(s)", and `get_review_history` in the agent trace.
4. To reset, record *Reject* on the first investigation (removes it from the catalog) or clear `backend/.rulepilot_data` locally.

## 11. Demonstrate shadow scoring (mock bank feed)

1. Open **Transaction monitor** (`#monitor`). With no approved rules, click **Stream 20 transactions**: the baseline misses most synthetic card-testing fraud (red *Missed by all rules* rows).
2. Approve the card-testing candidate in **Investigations** (skill 10 step 2).
3. Back in the monitor, stream again. Rows marked **Caught only by approved rule** are fraud the approved rule would catch; the *Decision* column is unchanged because approved rules run in shadow.
4. Use **Score a transaction → Card-testing burst** to show one transaction: active *Allow*, shadow *Would flag*.

## 12. Diagnose agent failures

| Symptom in `model_run.errors` | Meaning | Action |
| --- | --- | --- |
| `503 UNAVAILABLE` | Model overloaded | Fallback handles it; retry later |
| `429 RESOURCE_EXHAUSTED` | Key quota or rate limit | Wait a minute; enable billing |
| Time limit reached | All models busy | Raise timeout or retry |
| Status `agent_incomplete`, no errors | Model never called `submit_findings` | Check trace; tighten prompt |
| Guardrail "Evidence quotes verified" failed | Model paraphrased quotes | Expected occasionally; it is shown to reviewers |
