# RulePilot AI

RulePilot AI is a foundation for continuous financial rule intelligence. Milestone 2A adds a small deterministic rule engine, transparent metrics, a fixed synthetic fixture, a baseline, candidate evaluation, and a bounded threshold-discovery experiment. Milestone 2B connects the React dashboard to those APIs for data-backed discovery, held-out backtesting, false-negative evidence, and proposal review status. The work is local and inspectable: it does not call an AI service or execute generated code.

## Architecture

- `backend/app/rules/models.py` defines strict Pydantic transaction and rule schemas. Ruleable fields come from metadata on the synthetic transaction schema. Unknown fields, extra properties, non-finite values, duplicate conditions, and unsupported operators are rejected.
- `backend/app/rules/engine.py` evaluates only the six explicit comparison operators. It never uses `eval`, `exec`, shell commands, or generated Python. A malformed rule raises a Pydantic validation error; missing or invalid transaction features fail closed and return `false`.
- `backend/app/evaluation.py` calculates the confusion matrix, precision, recall, false-positive rate, and counts. A zero denominator produces `0.0`; empty aligned inputs are valid.
- `backend/app/data.py` deterministically generates 120 synthetic labeled transactions and reproducible stratified train, validation, and test splits. The synthetic outcomes come from a noisy feature-based risk process; they are illustrative, not real customer data or a calibrated fraud model.
- `backend/app/baseline.py` defines the documented baseline: flag amount greater than or equal to 1,500 synthetic currency units. It is a comparison fixture, not a production recommendation.
- `backend/app/discovery.py` derives at most eight thresholds per eligible numeric feature from training feature values. It evaluates non-degenerate rules with minimum support on training, selects by validation F1 (then precision, recall, and false-positive rate), and evaluates the selected candidate once on the held-out test records. The discovery selection function accepts only training and validation data; the test split is passed only to final reporting.
- FastAPI endpoints are wired in `backend/app/api.py`; rule models, execution, metrics, data, and discovery remain usable without FastAPI.
- The dashboard loads API health, the baseline catalog, and discovery/split information from the backend. Backtest comparisons and missed-fraud IDs come from the held-out backtest response. Only transaction IDs are displayed in the false-negative table.

Candidates are returned as drafts with their exact condition and validation/test evidence. Candidate results are not guaranteed to outperform the baseline. Compare the reported held-out metrics and false positives; do not treat a result from the synthetic fixture as evidence about real payment traffic.

## Rule JSON example

```json
{
  "rule_id": "TEAM-AMOUNT-001",
  "name": "High amount review",
  "description": "Flags a transaction above the example threshold.",
  "rationale": "Illustrates an explicit numeric condition for review.",
  "conditions": [
    { "field": "amount", "operator": "greater_than", "value": 1250 }
  ],
  "logical_operator": "and",
  "status": "draft",
  "version": 1,
  "created_by": "analyst"
}
```

Available fields: `amount`, `account_age_days`, `transactions_24h`, and `distance_from_home_km`. Available comparison operators: `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`, `equals`, and `not_equals`. Multiple conditions can use `and` or `or`. Status must be one of `draft`, `pending_review`, `approved`, or `rejected`. Rule IDs use letters, numbers, dots, underscores, and hyphens; IDs must be unique within a rule catalog. The baseline ID `RP-BASELINE-001` is reserved.

## API

Run the backend as described below, then use `http://127.0.0.1:8000/docs` for the interactive schema and API explorer.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | API identity and health link |
| `GET` | `/health` | Process health status |
| `GET` | `/api/v1/rules` | List the documented baseline rule |
| `POST` | `/api/v1/rules/evaluate` | Validate and evaluate a supplied rule on synthetic samples; returns IDs, predictions, and metrics, not transaction features |
| `POST` | `/api/v1/backtests/run` | Compare a supplied candidate with the baseline on the same deterministic held-out test split |
| `POST` | `/api/v1/rules/discover` | Generate thresholds from train, select on validation, then evaluate once on test |

Example PowerShell calls, from any directory with the backend running:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/rules'

$candidate = @{
    rule_id = 'TEAM-AMOUNT-001'
    name = 'High amount review'
    description = 'Flags a transaction above the example threshold.'
    rationale = 'Illustrates an explicit numeric condition for review.'
    conditions = @(@{ field = 'amount'; operator = 'greater_than'; value = 1250 })
    logical_operator = 'and'
    status = 'draft'
    version = 1
    created_by = 'analyst'
}
$body = @{ candidate_rule = $candidate; seed = 41 } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/backtests/run' -Method Post -ContentType 'application/json' -Body $body

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/rules/discover' -Method Post -ContentType 'application/json' -Body '{"seed":41}'
```

The backtest response places baseline and candidate metrics side by side and lists synthetic fraud IDs missed by both the baseline and candidate on the test split. Discovery reports the selected candidate, its validation metrics, one held-out candidate evaluation, baseline test metrics, split sizes, and the missed baseline IDs. It does not assert that the candidate is better.

## Windows PowerShell setup

Requirements: Python 3.11 or newer, Node.js 20 or newer, npm, and Windows PowerShell.

### Backend

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks venv activation, run these from `backend` instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is at `http://127.0.0.1:8000`; interactive docs are at `/docs`.

### Frontend dashboard

In a second PowerShell window, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open Vite's printed local URL, normally `http://localhost:5173`. The dashboard reads the backend base URL from `VITE_API_BASE_URL`; by default it uses `http://localhost:8000`. To change it, copy the root `.env.example` to `frontend/.env.local`, set `VITE_API_BASE_URL`, and restart Vite. The backend currently has no persistent approve/reject endpoint, so the candidate remains a draft pending review; the dashboard does not simulate a decision or activate rules.

### Run backend tests

From the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

If you activated the backend virtual environment, use `python -m pytest -q` from `backend`.

### Run frontend checks

From the repository root:

```powershell
cd frontend
npm test
npm exec -- tsc -b --pretty false
npm run build
```

## Limitations

- Only synthetic records are included. No customer data or full public fraud dataset is bundled.
- The baseline threshold and label-generation process are illustrative and have no real-world calibration.
- Discovery currently searches one-condition numeric thresholds; it is a small, inspectable proposal mechanism, not machine learning or an autonomous rule author.
- Validation is used to select a candidate. The held-out test split is used only after selection, but the small synthetic sample makes metrics noisy.
- There is no persistence, authentication, human-approval workflow, production transaction ingestion, drift monitoring, or real-data backtesting yet.
- Candidate proposals are drafts. Human review and approval are not implemented in this milestone.

## Environment files

The root `.env.example` contains only the frontend API URL placeholder. `backend/.env.example` contains a local development label. No credentials or external service keys are needed.
