# Frontend Route and Page Matrix

The frontend uses a page-state router in `frontend/src/App.tsx`; the visible keys below are application routes/pages rather than React Router URL declarations.

| Page key / URL behavior | Component | Purpose | Guard | Main backend dependencies | Status |
|---|---|---|---|---|---|
| `home` | `Home.tsx` | Entry and start flow | `ProtectedRoute` | session/check-in state | `IMPLEMENTED_AND_ACTIVE` |
| `checkin` | `CheckIn.tsx` | Check-in input | `ProtectedRoute` | sessions/check-in | `IMPLEMENTED_AND_ACTIVE` |
| `chat` / `/chat` | `Chat.tsx` -> `MultimodalChat textOnly` | Text conversation | `CHAT_USE` | conversations/messages | `IMPLEMENTED_AND_ACTIVE` |
| `multimodal` | `MultimodalChat.tsx` | Text/image/audio/video upload conversation | `MULTIMODAL_USE` | files, conversations/messages | `PARTIALLY_IMPLEMENTED` |
| `relaxation` | `Relaxation.tsx` | Interventions | `ProtectedRoute` | interventions | `IMPLEMENTED_AND_ACTIVE` |
| `report` | `Report.tsx` | User report/feedback | `CONVERSATION_READ_OWN` | report/feedback | `PARTIALLY_IMPLEMENTED` |
| `video` | `VideoCompanion.tsx` | Camera companion placeholder | `MULTIMODAL_USE` | no complete active workflow | `MOCK_OR_PLACEHOLDER` |
| `knowledge` | `KnowledgeReview.tsx` | KB review/publication | `KNOWLEDGE_REVIEW` | knowledge status/sources/chunks/publish | `IMPLEMENTED_AND_ACTIVE` |
| `humanEvaluation` | `HumanEvaluationReview.tsx` | Human evaluation scoring | `EVALUATION_REVIEW` | evaluation review routes | `IMPLEMENTED_AND_ACTIVE` |
| `evaluation` | `EvaluationDashboard.tsx` | Evaluation run/compare | `EVALUATION_RUN_CREATE` | evaluation registry/run/runs/compare | `IMPLEMENTED_AND_ACTIVE` |
| `developer` | `DeveloperDashboard.tsx` | Agent/RAG diagnostics | `RAG_DEBUG_VIEW` | debug agent/RAG/retrieval | `IMPLEMENTED_AND_ACTIVE` |
| `admin` | `AdminDashboard.tsx` | User/system/audit management | `USER_MANAGE` | admin users/system/audit | `IMPLEMENTED_AND_ACTIVE` |
| denied fallback | `AccessDenied.tsx` | Unauthorized page | component fallback | no privileged backend call | `IMPLEMENTED_AND_ACTIVE` |

Frontend guards are not treated as security controls; matching backend permission dependencies were checked for sensitive APIs.
