# agentic/ — context for AI coding assistants

This folder is the single source of project context for AI coding assistants (Claude Code, Codex, Gemini CLI, Copilot) and for new human contributors. Root `AGENTS.md` and `CLAUDE.md` point here.

Read in this order:

| File | Read when | Contents |
| --- | --- | --- |
| [context.md](context.md) | Always, first | Product, competition constraints, current status, key decisions |
| [guardrails.md](guardrails.md) | Before changing any code | Non-negotiable safety, evaluation, and governance rules |
| [architecture.md](architecture.md) | Before touching the backend | Module map, data flow, API reference, configuration |
| [skills.md](skills.md) | When doing a task | Step-by-step procedures for recurring tasks |
| [tasks.md](tasks.md) | When choosing what to do next | Milestones, backlog, and definition of done |
| [ui-guide.md](ui-guide.md) | Before touching the frontend or demoing | Every UI component and how to use it |
| [session-log.md](session-log.md) | At the start and end of every session | Current handoff and per-session log, so work resumes in a new context window |

## Keeping this folder accurate

- Update `context.md` "Current status" and `tasks.md` at the end of every milestone.
- If code and these documents disagree, the code wins; fix the document in the same change.
- Never put credentials, API keys, or personal data in this folder.
