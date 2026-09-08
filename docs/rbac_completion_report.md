# CARE-Psy RBAC Completion Report

Date: 2026-09-03

## Summary

The CARE-Psy project now has a lightweight RBAC system with exactly four roles:

- `user`
- `reviewer`
- `developer`
- `admin`

Backend authorization is enforced through permission dependencies, not only frontend route hiding. Ordinary psychological conversations remain private by owner id, and there is no admin/developer permission for reading all user chat history.

## Backend Work Completed

Added:

- `backend/auth/permissions.py`
- `backend/auth/service.py`
- `backend/auth/schemas.py`
- `backend/auth/dependencies.py`
- `backend/routers/knowledge.py`
- `backend/routers/evaluation.py`
- `backend/routers/debug.py`
- `backend/tests/test_rbac.py`

Updated:

- `backend/database/models.py`
- `backend/database/db.py`
- `backend/config.py`
- `backend/middleware.py`
- `backend/main.py`
- `backend/routers/auth.py`
- `backend/routers/admin.py`
- `backend/routers/chat.py`
- `backend/routers/multimodal.py`
- `backend/routers/conversations.py`
- `backend/routers/files.py`
- `backend/routers/jobs.py`
- `backend/routers/sessions.py`
- `backend/routers/feedback.py`
- `backend/routers/interventions.py`
- `backend/routers/report.py`
- `backend/routers/stt.py`

Key behavior:

- Real user registration/login with bearer tokens.
- Registration defaults to role `user`.
- Higher roles are admin-managed.
- Inactive users are rejected.
- Last active admin is protected from deactivation/demotion.
- Sensitive routes require real database users.
- Chat/demo/local routes can explicitly allow synthetic demo users.
- Conversation reads/writes/deletes remain scoped to the principal's `owner_id`.
- Chat payloads are sanitized for roles without debug permissions.
- Admin system status exposes only configured/masked secret state, not raw API keys.
- Role changes and production KB publish/rollback actions are audit-logged.
- Knowledge review decisions are audit-logged.
- Existing public-demo access-code flow is preserved.

## Frontend Work Completed

Added:

- `frontend/src/auth/rbac.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/components/ProtectedRoute.tsx`
- `frontend/src/pages/AccessDenied.tsx`
- `frontend/src/pages/KnowledgeReview.tsx`
- `frontend/src/pages/HumanEvaluationReview.tsx`
- `frontend/src/pages/DeveloperDashboard.tsx`
- `frontend/src/pages/AdminDashboard.tsx`

Updated:

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/files.ts`
- `frontend/src/types/api.ts`
- `frontend/src/pages/MultimodalChat.tsx`
- `frontend/src/styles.css`

Key behavior:

- SPA is wrapped in `AuthProvider`.
- Account panel supports login/register/logout.
- Navigation is filtered by permission.
- Protected pages render `AccessDenied` when unauthorized.
- API client sends bearer tokens automatically.
- Media preview URLs include bearer-token fallback for browser media tags.
- Multimodal internal analysis hides agent trace/RAG/source/metrics panels unless the user has debug permissions.

## Documentation

Added:

- `docs/rbac_prebuild_audit.md`
- `docs/rbac_permission_matrix.md`
- `docs/rbac_architecture.md`
- `docs/rbac_completion_report.md`

## Verification

Commands run:

```powershell
python -m pytest backend\tests\test_rbac.py -q
```

Result:

```text
22 passed
```

Command run:

```powershell
python -m pytest backend\tests -q
```

Result:

```text
109 passed, 6 warnings in 104.31s
```

Command run:

```powershell
cd frontend
npm run build
```

Result:

```text
tsc && vite build completed successfully in 1.21s
```

Warnings observed were existing dependency/framework deprecation warnings from pytest-asyncio, FastAPI `on_event`, and `pkg_resources`; no RBAC test failures or frontend build errors remain.
