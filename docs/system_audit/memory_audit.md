# Memory Audit

## Active Memory

Conversation messages are persisted in SQLite. A local-rules memory service updates user memory/profile information, and summaries are rebuilt from recent conversation history. The current setting `memory_enabled=true` activates per-session memory behavior.

## Disabled or Missing Memory

`global_memory_across_conversations=false`, so cross-conversation global memory is disabled. Semantic LLM memory extraction and embedding-based memory recall were not found in the active path. Memory privacy controls, retention automation, deletion UX, and user-visible memory management are incomplete or require separate confirmation from the routes.

## Data Evidence

The current database contains 36 summaries, 93 memory settings rows, and 69 user memory items. Tests used a separate temporary database and did not alter these records.

| Capability | Status |
|---|---|
| Session conversation memory | `IMPLEMENTED_AND_ACTIVE` |
| Local profile/memory rules | `IMPLEMENTED_AND_ACTIVE` |
| Global cross-conversation memory | `IMPLEMENTED_BUT_DISABLED` |
| LLM semantic memory | `NOT_IMPLEMENTED` |
| Complete retention/privacy lifecycle | `PARTIALLY_IMPLEMENTED` |


