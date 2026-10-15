# Guardrails — rules every change must keep

These are product requirements, not style preferences. A change that breaks one is a bug even if tests pass.

## Model and agent

1. The model never executes code. No `eval`, `exec`, generated Python, SQL, or shell. Rules are data validated by `app/rules/models.py`.
2. The agent has only the tools in `InvestigationToolkit.agent_tools()`. Never add network, file, shell, database, or arbitrary-HTTP tools.
3. Every tool validates input, is bounded, and returns `{"ok": false, "error": ...}` instead of raising.
4. Agent bounds stay configured: max model calls (`RULEPILOT_AGENT_MAX_LLM_CALLS`), timeout, ≤ 3 candidates, ≤ 3 conditions, advisory size limits.
5. Advisory text and reviewer comments are **untrusted data**. They are delimited in the prompt and never concatenated into instructions.
6. The agent's claims are re-checked in Python: quotes are verified against the source, coverage is recomputed, the selected rule must be one it evaluated.

## Evaluation integrity

7. The agent sees training statistics and validation results only. **The test split is never reachable from a tool.**
8. `run_final_holdout` runs once per investigation, called by the orchestrator, only for the agent's selected candidate.
9. All metrics come from `app/evaluation.py` using real predictions and labels. The model never reports or edits metrics.
10. Keep seeds, dataset IDs and versions, model ID, and advisory SHA-256 in every report and audit event.
11. Never tune thresholds, prompts, or datasets against held-out test results.

## Governance

12. Candidate rules are always created as `draft` by `rulepilot-agent`.
13. Human approval is recorded separately, and **only a human approval activates a rule** (team decision, 16 Oct 2026; before that, approval never activated). Reject or request-changes deactivates it. Activation and deactivation are audited (`activation` on the review record, `rule_added_to_catalog` / `rule_removed_from_catalog`). The model can never approve, activate, or deactivate anything. Shadow evaluation remains supported for rules that should be trialled without deciding.
14. The audit log is append-only.
15. Approved rules enter the reviewed catalog as active; a later reject or request-changes removes them. The agent may read the catalog and review history but can never write to either.

## Honesty

16. Synthetic data is labelled as synthetic everywhere it appears. The injected card-testing pattern is disclosed.
17. Never claim real-world detection rates, loss prevention, or ROI.
18. If an advisory cannot be tested with available fields, the system must say so (`not_testable`) rather than map it onto unrelated fields.

## Secrets and data

19. Credentials live only in `backend/.env` (git-ignored) or Secret Manager. Never in source, fixtures, recordings, docs, logs, or the frontend.
20. The frontend never calls Gemini directly.
21. Only include third-party text we have rights to; store short attributed excerpts with the source URL.

## Compatibility

22. Existing endpoints and response fields stay backward compatible; add fields, don't rename them.
23. All existing tests must pass. New behaviour needs tests that do not call Gemini (use a fake agent runner).
