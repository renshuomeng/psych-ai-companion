# CARE-Psy RBAC Architecture

Date: 2026-09-03

## Goal

The RBAC layer adds real user accounts and role-based access control without changing the project's privacy baseline: psychological chat data remains private to the conversation owner by default.

## Authentication

Human accounts are stored in the new `users` table:

- `id`
- `username`
- `email`
- `password_hash`
- `role`
- `is_active`
- timestamps

Passwords are hashed with standard-library PBKDF2-SHA256. API clients authenticate with a bearer token issued by:

```text
POST /api/auth/login
POST /api/auth/register
GET /api/auth/me
```

Registration always creates a `user` role. Higher roles must be assigned by an admin.

The existing public-demo access-code cookie remains as an outer demo gate. It maps to a synthetic `user` principal and can only reach routes that explicitly allow demo users.

## Principal Model

`backend/auth/dependencies.py` converts the request into a `CurrentPrincipal`.

Real account owners use:

```text
owner_id = user:<user_id>
```

Public demo owners use:

```text
owner_id = access:<hashed_session_id>
```

Local development without public access keeps the previous `X-Conversation-Owner` fallback for demo convenience.

## Authorization

Every sensitive route is guarded by backend dependencies:

- `require_permission(permission)`
- `require_any_permission(...)`

End-user chat and own-conversation routes pass `allow_demo_user=True`. Reviewer, developer, and admin features require a real database user even if public-demo access is enabled.

## Conversation Isolation

Conversation access is enforced by:

```text
ensure_own_conversation(db, conversation_id, principal)
```

The guard checks that:

- the conversation exists
- `conversation.owner_id == principal.owner_id`
- the conversation is not archived

Admin and developer roles do not bypass this guard. There is no backend permission for reading all ordinary user chats.

## Privacy Sanitization

Chat and conversation responses are sanitized before returning to roles without debug permissions.

Hidden without `AGENT_TRACE_VIEW`:

- `agent_trace`
- `psychological_state`
- `strategy_plan`
- `request_metrics`
- detailed risk reason internals

Hidden without `RAG_DEBUG_VIEW`:

- `knowledge_sources`
- `retrieval`
- `rag_route`
- `provider_metadata`

This keeps competition/debug observability available to developer/admin accounts while keeping normal psychological companion usage privacy-first.

## Admin Bootstrap

An initial admin can be created from environment variables:

```env
INITIAL_ADMIN_USERNAME=
INITIAL_ADMIN_EMAIL=
INITIAL_ADMIN_PASSWORD=
```

No default admin password is hardcoded. If these variables are empty, no initial admin is created automatically.

## Database Migration

`init_db()` creates the new RBAC tables through SQLAlchemy metadata and runs lightweight SQLite migrations for columns/indexes. If an existing SQLite database does not yet have a `users` table, the database file is copied to:

```text
backend/database/backups/
```

before RBAC tables are created.

## Audit Logs

Two audit tables support reviewer/admin accountability:

- `knowledge_review_audit_log`
- `admin_audit_log`

Role changes, user creation, production KB publish/rollback, and knowledge review decisions are logged with actor id, target id, action, timestamp, and compact metadata. The logs do not store private psychological chat text.

## Frontend Flow

The SPA now has an account panel, guarded navigation, and RBAC-specific pages:

- Knowledge Review
- Human Evaluation
- Developer Dashboard
- Administration

The frontend uses:

```text
frontend/src/auth/rbac.ts
frontend/src/auth/AuthContext.tsx
frontend/src/components/ProtectedRoute.tsx
```

These guards are for navigation clarity only. Backend authorization remains authoritative.
