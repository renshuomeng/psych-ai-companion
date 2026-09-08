# RBAC and Authentication Audit

## Roles and Permissions

Observed roles are user, reviewer, developer, and admin. The permission catalog contains 32 permissions. Approximate grants observed: user 5, reviewer 14, developer 19, admin 32.

The API uses principal ownership, permission checks, and response sanitization. Frontend navigation and pages are permission-gated, but backend authorization remains the security boundary.

## Active Authentication

- Registration creates `Role.USER`.
- Login, current-user, session, access, and logout routes are present.
- Admin routes cover users, audit, system, KB, and evaluation operations.
- The current database has one active admin account.

## Configuration Findings

The current effective settings report `AUTH_JWT_SECRET`, `PUBLIC_SESSION_SECRET`, and `INITIAL_ADMIN_PASSWORD` as configured. Secret contents are deliberately excluded. Production deployment hardening and rotation policy were not independently verified because the current app environment is development.

## Status

- RBAC enforcement: `IMPLEMENTED_AND_ACTIVE`.
- Owner and permission sanitization: `IMPLEMENTED_AND_ACTIVE`.
- Stable production secret configuration: `PARTIALLY_IMPLEMENTED`.
- Legacy `ADMIN_ACCESS_CODE` example configuration: `IMPLEMENTED_BUT_NOT_WIRED`.
- SSO, MFA, password reset, and account recovery: `NOT_IMPLEMENTED` unless separately provided by infrastructure.

## Effective Permission Matrix

| Role | Effective permission count | Main backend access |
|---|---:|---|
| user | 5 | Own chat/conversations, multimodal use, own settings |
| reviewer | 14 | User access plus KB source/chunk review, evaluation view/review/score/export, benchmark view |
| developer | 19 | User access plus agent trace, RAG debug/benchmark, evaluation run/compare/full, development config/prompt/model controls |
| admin | 32 | Developer/reviewer access plus production model/config, KB publish/rollback, role/user management, secret status |

Sensitive endpoints were checked in backend routers: evaluation uses `EVALUATION_*`, knowledge review/publish uses knowledge and production permissions, debug uses `AGENT_TRACE_VIEW`/`RAG_DEBUG_VIEW`, and admin uses `USER_MANAGE`, `ROLE_MANAGE`, or `SECRET_STATUS_VIEW`. Frontend hiding is supplementary; the backend guards are the actual boundary.

Conversation isolation is enforced in `conversation_service._conversation_query()` by conversation ID plus normalized owner ID, and file access checks owner/conversation permission in the files router. The audit did not mutate or attempt access to another real user's conversation.
