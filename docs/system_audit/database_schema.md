# Database Schema and Data State

## Database

Current database path:

`backend/database/psych_ai.sqlite`

The audit found real local application data. It did not modify this database. Backend tests used a separate temporary SQLite database.

## Observed Counts

| Table | Rows |
|---|---:|
| users | 1 |
| chat_message | 330 |
| conversation | 151 |
| conversation_summary | 36 |
| memory_settings | 93 |
| user_memory_item | 69 |
| risk_state | 92 |
| retrieval_log | 2,199 |
| request_metric | 88 |
| evaluation_run | 81 |
| knowledge_chunk | 20,093 |
| knowledge_chunks_fts | 20,093 |
| knowledge_source | 6 |
| feedback | 0 |
| multimodal_job | 0 |
| attachment | 0 |
| human_evaluation_review | 0 |
| admin_audit_log | 0 |

## Complete User Database Table Inventory

The SQLite schema also contains these FTS support tables: `knowledge_chunks_fts_config` (1), `knowledge_chunks_fts_content` (20,093), `knowledge_chunks_fts_data` (5,198), `knowledge_chunks_fts_docsize` (20,093), and `knowledge_chunks_fts_idx` (3,522). The application tables are `users`, `conversation`, `chat_message`, `conversation_summary`, `memory_settings`, `user_memory_item`, `risk_state`, `retrieval_log`, `request_metric`, `attachment`, `multimodal_job`, `intervention_session`, `feedback`, `evaluation_case`, `evaluation_run`, `human_evaluation_review`, `knowledge_source`, `knowledge_chunk`, `knowledge_review_audit_log`, and `admin_audit_log`.

All counts above were read from the current SQLite file. No row was inserted, updated, deleted, or reviewed by this audit.

## Interpretation

The application has persisted chat, memory, risk, retrieval, and evaluation history. There is one active admin account; credentials are deliberately excluded from this report. The zero counts for attachments, jobs, reviews, feedback, and admin audit records mean those workflows have no current local evidence, not that their routes are absent.

The database knowledge tables are not the same data plane as the active RAG V1 registry/index files. This dual representation is a maintenance and provenance risk.

