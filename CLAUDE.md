# Instructions for AI coding assistants

All project context lives in [`agentic/`](agentic/README.md). Before making changes:

1. Read [`agentic/context.md`](agentic/context.md) — product, competition constraints, current status.
2. Follow [`agentic/guardrails.md`](agentic/guardrails.md) — non-negotiable rules (no code execution by the model, test split never visible to the agent, approval never activates rules, no secrets in git).
3. Use [`agentic/skills.md`](agentic/skills.md) for procedures (setup, checks, adding tools or advisories, deployment).
4. Check [`agentic/tasks.md`](agentic/tasks.md) for what to work on next.
5. Frontend work: [`agentic/ui-guide.md`](agentic/ui-guide.md).

Before finishing any change, run the checks in skills.md skill 2 and update the docs listed in the definition of done.
