# Memory Orchestrator

Use the `memory-orchestrator` MCP server to save, search, and manage durable
memories across Codex sessions.

Before starting substantial work in a project, search memory for relevant
project and feedback entries. Save durable facts when the user reveals lasting
preferences, project decisions, corrected behavior, or external references.

Memory types:
- `user`: durable facts about the user. Save globally.
- `feedback`: corrections or confirmed approaches for agent behavior.
- `project`: durable technical facts, architecture, requirements, or decisions.
- `reference`: pointers to external resources.

Do not save ephemeral task progress, facts already obvious from the codebase, or
anything likely to change within this session.
