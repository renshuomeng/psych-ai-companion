# Runtime Wiring Map

This is the observed implementation path, not a design proposal.

| Frontend page/component | Frontend API | Backend router/endpoint | Service/agent | Model/index/storage | Status |
|---|---|---|---|---|---|
| `Chat.tsx` -> `MultimodalChat.tsx` with `textOnly` | `sendConversationMessage` | `POST /api/conversations/{conversation_id}/messages` | `conversation_service.send_conversation_message` -> `run_multimodal_flow` | Risk/Emotion/Agent V2/RAG V1/ARK/Safety -> SQLite | `IMPLEMENTED_AND_ACTIVE` |
| `MultimodalChat.tsx` | `uploadFile`, `sendConversationMessage` | `/api/files`, then conversation message endpoint | `process_attachments` -> `multimodal_agent` | ARK vision, Volc ASR, video/ffmpeg -> attachment/message rows | `PARTIALLY_IMPLEMENTED` |
| `VideoCompanion.tsx` | No complete active companion workflow | No verified dedicated camera-analysis endpoint | Placeholder UI | Planned face-api/equivalent text only | `MOCK_OR_PLACEHOLDER` |
| `Home.tsx` / `CheckIn.tsx` | Check-in client calls | `/api/sessions/...` and conversation payload | Session/check-in services | SQLite session/check-in state | `IMPLEMENTED_AND_ACTIVE` |
| `Relaxation.tsx` | Intervention start/complete/feedback | `/api/interventions/...` | Intervention service | SQLite intervention session/feedback | `IMPLEMENTED_AND_ACTIVE` |
| `Report.tsx` | `getReport` | `GET /api/report` | Report router/service | SQLite feedback/metrics | `PARTIALLY_IMPLEMENTED` |
| `EvaluationDashboard.tsx` | registry/run/list/compare clients | `/api/evaluation/registry`, `/run`, `/runs`, `/compare` | Evaluation runner/registry/metrics | Local datasets, result files, `EvaluationRun` | `IMPLEMENTED_AND_ACTIVE` |
| `HumanEvaluationReview.tsx` | review cases/score/export | `/api/evaluation/review/*` | Human review router | `HumanEvaluationReview` + result files | `IMPLEMENTED_AND_ACTIVE` |
| `KnowledgeReview.tsx` | status/sources/chunks/review/publish clients | `/api/knowledge/*` | KB registry/review/index builder | Registry JSONL, CSV review, BM25/Chroma | `IMPLEMENTED_AND_ACTIVE` |
| `DeveloperDashboard.tsx` | debug agent/RAG/retrieval | `/api/debug/*` | Debug router -> active services | Permission-gated trace/index data | `IMPLEMENTED_AND_ACTIVE` |
| `AdminDashboard.tsx` | users/system/audit clients | `/api/admin/*` | Admin router/RBAC | Users and admin audit tables | `IMPLEMENTED_AND_ACTIVE` |

## Primary Chat Detail

`MultimodalChat.send()` creates an optimistic user row, uploads files before sending, calls `sendConversationMessage`, receives `user_message` and `assistant_message`, replaces the optimistic row, and refreshes the conversation list. The backend persists user and assistant rows before returning the response.

## Paths That Exist but Are Not Primary

`sendChat` calls `POST /api/chat`, but the current primary pages use conversation endpoints. Async `/api/multimodal/jobs` clients exist, but the main multimodal page uses synchronous conversation processing. The dedicated `/api/stt` route exists but is placeholder-level.
