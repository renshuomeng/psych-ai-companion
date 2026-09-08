# CARE-Psy RBAC Prebuild Audit

Date: 2026-09-03

## Scope

This audit covers the current CARE-Psy / `psych-ai-companion` project before adding the competition-focused RBAC layer.

Scanned areas:

- `backend/`
- `frontend/`
- `evaluation/`
- `scripts/`
- `backend/tests/`

Search terms reviewed in source files: `auth`, `user`, `login`, `jwt`, `token`, `session`, `role`, `permission`, `evaluation`, `knowledge`, `review`, `rag`, `agent`, `admin`.

## Current Authentication Structure

The project currently has a public-demo access gate, not a human user authentication system.

- `backend/services/auth_service.py` creates and verifies a signed HMAC access cookie named `psych_ai_access`.
- `backend/routers/auth.py` exposes:
  - `GET /api/auth/session`
  - `POST /api/auth/access`
  - `POST /api/auth/logout`
- `backend/middleware.py` uses `PublicAccessMiddleware` to require the demo access cookie for non-exempt `/api/*` routes when `PUBLIC_ACCESS_ENABLED=true`.
- No JWT user login exists yet.
- No password login exists yet.
- No `users` table exists in the current SQLite database.

## Existing User Data Structure

There is no formal user model yet.

Conversation ownership is currently represented by `Conversation.owner_id`:

- Public demo mode maps the signed access session id to `access:<hash>`.
- Local development mode can use `X-Conversation-Owner`.
- Fallback owner is `local`.

This provides conversation isolation by owner id, but does not provide role, account, active/inactive state, password hashing, or admin-managed users.

## Current JWT / Session / Cookie Status

- JWT: not present.
- Session: no database-backed user session.
- Cookie: present only for public-demo access code.
- Important compatibility constraint: the public-demo access code should remain available as an outer gate, while RBAC becomes the backend-enforced role/permission layer for sensitive APIs.

## Existing Pages

Frontend is a React/Vite SPA with manual page state in `frontend/src/App.tsx`; it does not use React Router.

Current pages include:

- Home
- CheckIn
- MultimodalChat
- Chat
- Relaxation
- Report
- VideoCompanion
- EvaluationDashboard

There is no unified `AuthContext`, `ProtectedRoute`, or `PermissionRoute` yet.

There is no dedicated Admin page yet.

There is no dedicated Knowledge Review page yet.

There is no dedicated Developer dashboard yet, although `EvaluationDashboard` already functions as a developer/evaluation surface.

## Existing API Surface

FastAPI routers are included from `backend/main.py`:

- `/api/health`
- `/api/auth`
- `/api/chat`
- `/api/chat/multimodal`
- `/api/conversations`
- `/api/files`
- `/api/multimodal/jobs`
- `/api/stt`
- `/api/feedback`
- `/api/report`
- `/api/sessions`
- `/api/interventions`
- `/api/admin`

Current admin APIs are under `backend/routers/admin.py` and use `X-Admin-Code` via `ADMIN_ACCESS_CODE`, not RBAC:

- Knowledge import/list/source/delete/rebuild
- Evaluation registry/run/list/detail/compare

## Evaluation Center Routes

Frontend route/page:

- Manual page key: `evaluation`
- UI label: `评测面板`
- Component: `frontend/src/pages/EvaluationDashboard.tsx`

Backend routes currently used by the frontend:

- `GET /api/admin/evaluation/registry`
- `POST /api/admin/evaluation/run`
- `GET /api/admin/evaluation/runs`
- `GET /api/admin/evaluation/runs/{run_id}`
- `POST /api/admin/evaluation/compare`

The evaluation runner writes outputs under `evaluation/results/` and keeps evaluation sessions isolated from normal conversation history.

## Knowledge Base Review Routes

There is no frontend Knowledge Review page yet.

Knowledge review currently exists mainly as scripts:

- `scripts/rag/review_sources.py`
- `scripts/rag/review_chunks.py`
- `scripts/rag/generate_kb_v2_reports.py`

Knowledge chunk review state is stored in JSONL files organized by status through `scripts/rag/kb_v11_utils.py`.

Existing admin knowledge APIs:

- `POST /api/admin/knowledge/import`
- `GET /api/admin/knowledge/sources`
- `GET /api/admin/knowledge/sources/{source_id}`
- `DELETE /api/admin/knowledge/sources/{source_id}`
- `POST /api/admin/knowledge/rebuild`

## Agent Trace / RAG Debug

No dedicated `/api/debug/*` router exists yet.

Current chat responses can include:

- `agent_trace`
- `knowledge_sources`
- `retrieval`
- `psychological_state`
- `strategy_plan`
- `rag_route`
- `request_metrics`

This is useful for competition debugging but should be sanitized for ordinary users after RBAC is added.

## Model And Prompt Configuration

Model configuration is centralized in `backend/config.py`:

- `ark_api_key`
- `ark_base_url`
- `doubao_model_id`
- `doubao_vision_model_id`
- `doubao_video_model_id`
- `eval_judge_provider`
- `eval_judge_model_id`

Prompt files are stored under:

- `backend/prompts/`

There is no full Prompt Editor UI yet, so this RBAC build should not introduce a complex prompt editor.

## Production Index Publishing

Production KB index publishing is script-based:

- `scripts/rag/build_production_indexes.py`

It builds approved-only BM25 and dense production indexes and supports BM25 rollback.

No RBAC-protected API currently wraps this flow.

## Conversation Association

Real chat history is tied to `Conversation.owner_id`.

The existing service already enforces owner matching in `services/conversation_service.py` by checking:

- `conversation.owner_id == owner_id`

This is a good base for RBAC. The RBAC implementation should map authenticated users to stable owner ids such as `user:<user_id>` and preserve legacy demo/local owner behavior for compatibility.

## Existing Users Table

SQLite schema inspection confirms:

- `users` table: absent
- `conversation.owner_id`: present
- `evaluation_run`: present
- `knowledge_source` and `knowledge_chunk`: present

## Planned New Files

Backend:

- `backend/auth/__init__.py`
- `backend/auth/permissions.py`
- `backend/auth/dependencies.py`
- `backend/auth/schemas.py`
- `backend/auth/service.py`
- `backend/routers/knowledge.py`
- `backend/routers/evaluation.py`
- `backend/routers/debug.py`
- `backend/tests/test_rbac.py`

Frontend:

- `frontend/src/auth/rbac.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/components/ProtectedRoute.tsx`
- `frontend/src/pages/AccessDenied.tsx`
- `frontend/src/pages/KnowledgeReview.tsx`
- `frontend/src/pages/DeveloperDashboard.tsx`
- `frontend/src/pages/AdminDashboard.tsx`

Docs:

- `docs/rbac_permission_matrix.md`
- `docs/rbac_architecture.md`
- `docs/rbac_completion_report.md`

## Planned Modified Files

Backend:

- `backend/database/models.py`
- `backend/database/db.py`
- `backend/config.py`
- `backend/services/auth_service.py`
- `backend/routers/auth.py`
- `backend/routers/admin.py`
- `backend/routers/chat.py`
- `backend/routers/multimodal.py`
- `backend/routers/conversations.py`
- `backend/routers/files.py`
- `backend/routers/jobs.py`
- `backend/routers/sessions.py`
- `backend/routers/report.py`
- `backend/routers/interventions.py`
- `backend/main.py`

Frontend:

- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/files.ts`
- `frontend/src/types/api.ts`
- `frontend/src/pages/EvaluationDashboard.tsx`
- `frontend/src/pages/MultimodalChat.tsx`
- `frontend/src/styles.css`

## Compatibility Risks

- Existing public-demo access code must remain usable and should continue protecting the public demo.
- Existing local development flow should not lose the ability to run chat quickly; a local/demo principal can remain available for ordinary user-mode chat.
- Sensitive APIs must not rely on the local/demo fallback. Evaluation, knowledge review, debug, admin, production publishing, and role management must require an active database user with the needed permission.
- Existing frontend uses manual page state, so route guards must be lightweight and compatible with the current app shell.
- Existing chat UI expects debug-rich response fields. Backend sanitization may make these fields empty for user-mode sessions, and frontend panels should handle that gracefully.
- SQLite migrations must be lightweight and must back up the existing database before adding RBAC tables/columns.
- Evaluation full runs must still honor `EVAL_ALLOW_PAID_FULL_RUN`; developer permission alone must not bypass the paid-run guard.
- Audit logs must avoid recording full private chat content.
