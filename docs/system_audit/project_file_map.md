# Project File Map

Audit date: 2026-09-07

## Scope

The project root is `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion`. The source inventory was collected with `rg --files` while excluding installed frontend dependencies, build output, Python caches, large uploaded files, Chroma indexes, BM25 indexes, model caches, and database backups.

The inventory contains 980 relevant source, configuration, evaluation, training, and documentation files. The project is not a Git repository at this path; the filesystem is therefore the audit source of truth.

## Top-Level Areas

| Area | Observed role | Audit status |
|---|---|---|
| `backend/` | FastAPI application, agents, services, routers, schemas, database, tests | `IMPLEMENTED_AND_ACTIVE` |
| `frontend/` | React/Vite user, admin, developer, evaluation, review, and multimodal pages | `IMPLEMENTED_AND_ACTIVE` |
| `evaluation/` | Datasets, adapters, runners, metrics, cached results | `PARTIALLY_IMPLEMENTED` |
| `training/` | SFT dataset preparation and reports | `IMPLEMENTED_AND_ACTIVE` |
| `scripts/` | KB, RAG, evaluation, and SFT operational scripts | `IMPLEMENTED_AND_ACTIVE` |
| `deployment/` | Deployment notes and operational material | `PARTIALLY_IMPLEMENTED` |
| `docs/` | User and audit documentation | `IMPLEMENTED_AND_ACTIVE` |
| `competition_results/`, `reports/`, `logs/`, `work/` | Generated outputs, reports, logs, temporary or experimental artifacts | `UNKNOWN` |

## Backend Map

- `backend/main.py`: application construction, startup/shutdown, routers, static SPA serving.
- `backend/routers/`: public API boundaries for auth, chat, conversations, files, multimodal jobs, STT, feedback, reports, sessions, interventions, knowledge, evaluation, debug, and admin.
- `backend/agents/`: coordinator, risk, emotion, multimodal, counselor, safety, intervention, memory, and psychological-state analysis.
- `backend/services/`: persistence, RAG V1, KB registry/index access, ARK, speech/video/image, jobs, auth, RBAC, memory, evaluation support, and legacy services.
- `backend/schemas/`: API and Agent V2 contracts.
- `backend/database/`: SQLAlchemy/SQLite schema and the current local database.
- `backend/tests/`: 18 test files; the audit run executed 109 tests against a temporary SQLite database.

## Frontend Pages

`AccessDenied`, `AdminDashboard`, `Chat`, `CheckIn`, `DeveloperDashboard`, `EvaluationDashboard`, `Home`, `HumanEvaluationReview`, `KnowledgeReview`, `MultimodalChat`, `Relaxation`, `Report`, and `VideoCompanion` are present. Presence of a page is not treated as proof that its backend capability is complete.

## Excluded Runtime Artifacts

The audit did not enumerate the contents of upload storage, Chroma databases, BM25 indexes, model caches, node modules, Python caches, or database backups as source files. Their existence and selected runtime metadata were checked separately where needed.


