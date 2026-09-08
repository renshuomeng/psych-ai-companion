# CARE-Psy Phase 0 Current System Audit

Generated: 2026-08-10

## Scope

This audit reflects the actual repository at `C:\Users\renshuomeng\Documents\Codex\2026-06-30\ban\psych-ai-companion`. The project directory is not currently a Git repository, so Git diff/status information is unavailable from this folder.

## Frontend Structure

- Framework: React + Vite + TypeScript.
- Entry: `frontend/src/App.tsx`.
- Main pages: Home, CheckIn, MultimodalChat, Chat, Relaxation, Report, VideoCompanion, EvaluationDashboard.
- Main components: attachment picker/preview, image/audio/video uploaders, audio recorder, camera recorder, media analysis, transcript, emotion, risk, intervention, knowledge sources, evidence panel, memory panel, system metrics, agent trace.
- API wrapper: `frontend/src/api/client.ts`, `frontend/src/api/files.ts`, `frontend/src/api/jobs.ts`.

## Backend Structure

- Framework: FastAPI.
- Entry: `backend/main.py`.
- Routers: health, auth, chat, multimodal chat, files, multimodal jobs, stt, feedback, report, sessions, interventions, admin.
- Database: SQLite via SQLAlchemy.
- Core services: media, image, video, speech, storage, RAG, retrieval, vector store, embedding, chunking, document parser, memory, metrics, sessions, cleanup.

## Database Tables

Current SQLite tables include:

- `attachment`
- `multimodal_job`
- `feedback`
- `chat_message`
- `knowledge_source`
- `knowledge_chunk`
- `knowledge_chunks_fts` and FTS backing tables
- `conversation_summary`
- `memory_settings`
- `user_memory_item`
- `risk_state`
- `retrieval_log`
- `intervention_session`
- `evaluation_run`
- `evaluation_case`
- `request_metric`

## API Surface

- `GET /api/health`
- `GET /api/auth/session`
- `POST /api/auth/access`
- `POST /api/auth/logout`
- `POST /api/chat`
- `POST /api/chat/multimodal`
- `POST /api/files/upload`
- `GET /api/files/{file_id}`
- `GET /api/files/{file_id}/preview`
- `DELETE /api/files/{file_id}`
- `POST /api/multimodal/jobs`
- `GET /api/multimodal/jobs/{job_id}`
- `DELETE /api/multimodal/jobs/{job_id}`
- `GET/POST /api/stt`
- `POST /api/feedback`
- `GET /api/report`
- `GET /api/report/session/{session_id}`
- `GET /api/sessions/{session_id}/privacy-summary`
- `DELETE /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/memory`
- `PATCH /api/sessions/{session_id}/memory-settings`
- `DELETE /api/sessions/{session_id}/memory`
- `POST /api/sessions/{session_id}/memory/rebuild`
- `POST /api/interventions/{intervention_id}/start`
- `POST /api/interventions/{intervention_id}/complete`
- `POST /api/interventions/{intervention_id}/feedback`
- `POST /api/admin/knowledge/import`
- `GET /api/admin/knowledge/sources`
- `GET /api/admin/knowledge/sources/{source_id}`
- `DELETE /api/admin/knowledge/sources/{source_id}`
- `POST /api/admin/knowledge/rebuild`
- `POST /api/admin/evaluation/run`
- `GET /api/admin/evaluation/runs`
- `GET /api/admin/evaluation/runs/{run_id}`

## Agent Flow

Current multimodal flow:

1. MultimodalAgent processes uploads and media outputs.
2. RiskAgent performs rule-first risk assessment from user text, audio/video transcript, and OCR.
3. EvidenceBuilder normalizes multimodal evidence.
4. MemoryAgent stores user turn, preferences, summaries, and risk state.
5. EmotionAgent infers emotion label, secondary emotions, intensity, dimensions, evidence, and uncertainty.
6. InterventionAgent recommends traceable interventions.
7. CounselorAgent calls Doubao/Volcengine Ark with RAG and context bundle.
8. SafetyAgent enforces safe output and high-risk crisis referral.
9. MemoryAgent stores assistant turn and updates summary.

## Doubao / Provider Calls

- Text generation uses Volcengine Ark Responses API through `backend/services/ark_client.py`.
- Image and video analysis also use Ark client; video supports provider-file analysis and keyframe fallback.
- Speech transcription is configured separately and currently reports unconfigured if credentials are absent.
- Provider failures are redacted and converted to structured `AppError`.

## Multimodal Processing

- Image: OCR, visual summary, observable cues, low-weight visual affect candidates.
- Audio: ffmpeg extraction and speech transcription when configured.
- Video: ffprobe validation, provider video analysis, fallback keyframe extraction, optional audio transcription.
- Safety rule: visual cues cannot independently trigger high-risk crisis flow.

## Context Management

- Recent messages are stored in `chat_message`.
- Rolling summary is stored in `conversation_summary`.
- User preferences are stored in `user_memory_item`.
- Risk state is stored separately in `risk_state`.
- Context builder estimates token budget and trims old recent messages first.

## Current RAG

- Knowledge documents are stored under `backend/data/knowledge_base`.
- Import pipeline: document parser -> cleaner -> semantic chunking -> embedding -> vector store.
- Current vector backend: SQLite-stored deterministic local hashing vectors.
- Keyword backend: SQLite FTS5 when available, Python keyword scoring fallback.
- ChromaDB is not currently installed in the active Python environment, so true ChromaDB persistence is not verified.

## Current Safety System

- RiskAgent has rule-first high-risk detection.
- It handles negation, third-party reports, quoted/news/literary contexts, plan/time/means cues, and harm-to-others cues.
- High risk bypasses ordinary CounselorAgent and InterventionAgent and returns a crisis referral template.
- SafetyAgent blocks diagnosis, medication advice, overpromise, and unsafe wording.

## Current Tests

- Backend pytest suite covers uploads, risk, speech, multimodal high-risk behavior, visual emotion, video fallback, RAG, memory, and session isolation.
- Frontend production build has been previously verified.
- Evaluation scripts exist for emotion, risk, RAG, memory, latency, and full evaluation.

## Deployment

- Local development: Vite on `5173`, FastAPI on `8001`.
- Public demo: FastAPI can serve production frontend and Cloudflare tunnel scripts exist.
- Dockerfile and docker-compose are present.

## Implemented Functions

- Text/image/audio/video input.
- File upload, preview, validation, deletion, retention cleanup.
- Risk-first safety flow.
- Doubao text/image/video integration.
- RAG source display.
- Memory viewer and controls.
- Intervention start/complete/feedback.
- Request metrics logging.
- Evaluation dashboard.

## Repeated or Legacy Code

- `backend/data/knowledge_base.json` is a legacy lightweight keyword KB and is now superseded by `backend/data/knowledge_base/`.
- `scripts/run_ablation.py` exists from an earlier phase, but ablation is explicitly out of scope for the current user request.
- Evaluation had `rag_queries.jsonl`; CARE-Psy `rag_cases.jsonl` has now been added and is used by the RAG runner.

## Architecture Issues

- ChromaDB is configured by path but not installed or verified.
- Current local hashing embedding is deterministic and useful for offline demos, but weaker than a real Chinese embedding model.
- Psychological state analysis is still rule/local heuristic based; Phase 4 asks for a structured state analyzer but this round stops at Phase 3.
- Evaluation datasets are small and synthetic; they are a baseline, not publishable evidence.
- Some frontend admin actions are visible in development and rely on backend admin checks.

## Initially Missing Functions For This Round

- `cause_cases.jsonl` and `strategy_cases.jsonl`.
- `safety_redteam.jsonl` alias required by CARE-Psy naming.
- `rag_cases.jsonl` alias required by CARE-Psy naming.
- Strategy evaluator and cause evaluator.
- Baseline comparison between Doubao direct and current agent without forcing expensive real API calls.
- JSON knowledge document import.
- CARE-Psy knowledge folder taxonomy.
- Emotion/cause/strategy/risk-aware retrieval scoring.
- NDCG@5 retrieval metric.

## Phase 1-3 Update

The missing items above were addressed after the initial audit, except for real Doubao direct baseline execution, which remains scaffolded but skipped by default to avoid unapproved API cost. ChromaDB remains unavailable in the current Python environment, so SQLite local vector retrieval is still the active backend.

## Recommended Files To Modify Next

- `backend/config.py`
- `backend/services/document_parser_service.py`
- `backend/services/chunking_service.py`
- `backend/services/knowledge_ingestion_service.py`
- `backend/services/retrieval_service.py`
- `backend/services/reranker_service.py`
- `evaluation/datasets/*`
- `evaluation/runners/*`
- `evaluation/metrics/retrieval_metrics.py`
- `scripts/test_rag_query.py`
- `README.md`
