# Multi-Conversation Chat Audit

Generated: 2026-08-11

## Pre-Upgrade Findings

- Current chat ID: the backend already used `session_id` for multimodal chat, memory, risk, attachments, jobs, retrieval logs, and metrics.
- Conversation table: there was no dedicated `conversation` table before this upgrade.
- Message persistence: `chat_message` already existed and was used by the multimodal memory flow, but the plain text Chat page did not pass a session id and only showed the latest response in React state.
- Refresh behavior: the multimodal page stored only one `psych-ai-session-id` in `localStorage`; it did not reload message history from SQLite, so the visible conversation could reset after refresh.
- Chat API history: `/api/chat` was a compatibility single-turn endpoint. The new frontend uses `/api/conversations/{conversation_id}/messages`.
- Memory isolation: existing memory tables were already keyed by `session_id`.
- Attachment isolation: existing attachments were already keyed by `session_id`; this upgrade adds `conversation_id` and `message_id`.
- Risk isolation: existing risk state was already keyed by `session_id`.

## Upgrade Decision

The business concept is now `Conversation`. For compatibility with the existing system:

```text
conversation_id == session_id
```

This preserves the working Memory/Risk/Attachment/RAG isolation paths and avoids rewriting the Agent system.

## Current Conversation Structure

`conversation`

- `id`: UUID string, also used as `session_id`.
- `owner_id`: browser/access-session owner.
- `title`
- `created_at`
- `updated_at`
- `last_message_at`
- `is_archived`
- `title_manually_set`
- `metadata_json`

## Current Message Structure

`chat_message`

- `message_id`
- `session_id`
- `conversation_id`
- `role`: `user`, `assistant`, or `system`
- `content`
- `sequence`
- `message_type`: `text` or `multimodal`
- `attachments_json`
- `metadata_json`
- `created_at`

## New APIs

- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `GET /api/conversations/{conversation_id}/messages`
- `PATCH /api/conversations/{conversation_id}`
- `DELETE /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/messages`

## Isolation Guarantees

- Messages: `WHERE conversation_id = current_id`.
- Memory: `session_id = conversation_id`.
- Summary: `conversation_summary.session_id = conversation_id`.
- Risk: `risk_state.session_id = conversation_id`.
- Attachments: `attachment.conversation_id = conversation_id`, with legacy fallback to `session_id`.
- Interventions: `intervention_session.session_id = conversation_id`.
- RAG logs/context: retrieval calls use the current `session_id`, which is the current conversation id.

## Migration

`scripts/migrate_conversations.py` backs up the SQLite database, applies idempotent schema updates, and registers old session data as legacy conversations. It does not delete old data.
