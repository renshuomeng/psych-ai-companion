# CARE-Psy RBAC Permission Matrix

Date: 2026-09-03

## Roles

This build defines exactly four roles:

- `user`
- `reviewer`
- `developer`
- `admin`

There are no implicit superuser roles and no "read all private conversations" permission.

## Permission Matrix

| Capability | user | reviewer | developer | admin |
| --- | --- | --- | --- | --- |
| Use text chat | yes | yes | yes | yes |
| Use multimodal chat and uploads | yes | yes | yes | yes |
| Read own conversations | yes | yes | yes | yes |
| Delete own conversations | yes | yes | yes | yes |
| View own settings/privacy state | yes | yes | yes | yes |
| View knowledge status/sources | no | yes | yes | yes |
| Review knowledge sources/chunks | no | yes | no | yes |
| Approve/reject knowledge sources/chunks | no | yes | no | yes |
| View evaluation registry/runs | no | yes | yes | yes |
| Human evaluation review/scoring/export | no | yes | no | yes |
| Create evaluation runs | no | no | yes | yes |
| Run full evaluation when enabled | no | no | yes | yes |
| Compare evaluation runs | no | no | yes | yes |
| View agent trace/debug payloads | no | no | yes | yes |
| View RAG debug/retrieval details | no | no | yes | yes |
| Run RAG benchmarks/ablations | no | no | yes | yes |
| Edit development config/prompts | no | no | yes | yes |
| Prepare production prompts | no | no | yes | yes |
| Switch production model/config | no | no | no | yes |
| Publish/rollback production KB | no | no | no | yes |
| Manage users | no | no | no | yes |
| Change roles | no | no | no | yes |
| View masked secret status | no | no | no | yes |

## Privacy Rules

- Ordinary psychological conversations are always scoped by owner id.
- Users, reviewers, developers, and admins can use the normal conversation APIs only for their own conversations.
- Backend guards do not expose a route that lists or reads every user's private chat history.
- User-facing chat responses are sanitized unless the requester has debug permissions:
  - agent trace is hidden from ordinary users and reviewers
  - psychological state and strategy plan internals are hidden from ordinary users and reviewers
  - RAG source lists and retrieval internals are hidden unless `RAG_DEBUG_VIEW` is present
  - provider metadata and request metrics are hidden unless debug permissions are present

## Backend Permissions

Central definitions live in:

```text
backend/auth/permissions.py
```

Sensitive routes use `require_permission(...)` or `require_any_permission(...)` from:

```text
backend/auth/dependencies.py
```

Public-demo and local-development synthetic principals are only allowed on explicitly marked end-user routes, such as chat and own-conversation flows. Admin, reviewer, developer, evaluation, knowledge review, and debug routes require a real database user.

## Frontend Guards

Frontend navigation and page access are guarded in:

```text
frontend/src/auth/rbac.ts
frontend/src/auth/AuthContext.tsx
frontend/src/components/ProtectedRoute.tsx
frontend/src/App.tsx
```

Frontend guards improve UX by hiding unavailable pages, but all security decisions are enforced again by the backend.
