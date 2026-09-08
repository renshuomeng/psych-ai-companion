# Feature Status Matrix

Only the following controlled status labels are used.

The engineering fields below reflect the current implementation and verification evidence. `Production Ready` is an assessment column, not one of the controlled status labels.

| Feature | Status | Evidence / boundary |
|---|---|---|
| Normal text chat | `IMPLEMENTED_AND_ACTIVE` | Conversation API and coordinator path |
| High-risk crisis referral | `IMPLEMENTED_AND_ACTIVE` | Risk-first deterministic branch |
| Rule risk detection | `PARTIALLY_IMPLEMENTED` | Active rules with semantic edge cases |
| Rule emotion detection | `IMPLEMENTED_AND_ACTIVE` | Active local heuristic |
| Agent V2 state/strategy/RAG route | `IMPLEMENTED_AND_ACTIVE` | Coordinator and tests |
| Counselor ARK generation | `IMPLEMENTED_AND_ACTIVE` | Active provider client |
| Rule safety post-processing | `IMPLEMENTED_AND_ACTIVE` | Active final safety step |
| LLM safety review | `IMPLEMENTED_BUT_NOT_WIRED` | Flag/fields exist; no active call |
| Session memory | `IMPLEMENTED_AND_ACTIVE` | DB messages/profile/summary |
| Global memory | `IMPLEMENTED_BUT_DISABLED` | Setting false |
| Image analysis | `IMPLEMENTED_AND_ACTIVE` | ARK vision path |
| Audio ASR in current env | `IMPLEMENTED_BUT_DISABLED` | Speech config absent |
| Video analysis | `PARTIALLY_IMPLEMENTED` | Provider/keyframe/audio fallback |
| Async multimodal jobs | `IMPLEMENTED_BUT_NOT_WIRED` | No worker found; main UI bypasses |
| STT endpoint | `MOCK_OR_PLACEHOLDER` | Placeholder service |
| TTS | `NOT_IMPLEMENTED` | No runtime implementation |
| Video companion | `MOCK_OR_PLACEHOLDER` | Placeholder page |
| RAG V1 production hybrid | `IMPLEMENTED_AND_ACTIVE` | Production BM25 + Chroma |
| Legacy RAG path | `IMPLEMENTED_BUT_DISABLED` | Fallback false |
| KB review/publication | `IMPLEMENTED_AND_ACTIVE` | Registry/status/index tooling |
| SFT preparation | `IMPLEMENTED_AND_ACTIVE` | 2,000-record selection artifact |
| Fine-tuned runtime model | `NOT_IMPLEMENTED` | No active model switch/use |
| Local smoke evaluation | `IMPLEMENTED_AND_ACTIVE` | Runner/results/dashboard |
| Official benchmark integration | `PARTIALLY_IMPLEMENTED` | Registry/compatible adapters |
| LLM judge | `NOT_IMPLEMENTED` | Heuristic metrics only |
| Human review workflow | `IMPLEMENTED_AND_ACTIVE` | Routes/page exist; no current rows |
| RBAC | `IMPLEMENTED_AND_ACTIVE` | Roles, permissions, owner checks |
| Stable production secrets | `PARTIALLY_IMPLEMENTED` | Current keys configured; production rotation/deployment not verified |
| Cost accounting | `NOT_IMPLEMENTED` | Rates unset and accounting unverified |
| Frontend automated tests | `NOT_IMPLEMENTED` | No test script |

## Required Audit Columns

| Feature | Purpose | Backend | Frontend | Runtime wired | Tested | Production ready | Status | Main issue |
|---|---|---|---|---|---|---|---|---|
| Text Chat | User support conversation | conversation router/service/coordinator | `Chat.tsx`/`MultimodalChat.tsx` | yes | backend tests/build | no unconditional claim | `IMPLEMENTED_AND_ACTIVE` | provider/runtime clinical validation |
| Psychological State | State hypothesis | `psychological_state_analyzer.py` | analysis metadata card | yes | Agent V2 tests/diagnostic | no | `IMPLEMENTED_AND_ACTIVE` | local rules only |
| Strategy | Response strategy | `services/strategy_planner.py` | analysis metadata card | yes | Agent V2 tests | no | `IMPLEMENTED_AND_ACTIVE` | local rules only |
| RAG | Knowledge retrieval | RAG V1 services/indexes | source cards/debug UI | yes | 162-case staged benchmark | no | `IMPLEMENTED_AND_ACTIVE` | production coverage split |
| Knowledge V2 | Registry/review/publication | knowledge router/scripts | `KnowledgeReview.tsx` | yes | registry/review paths | partial | `IMPLEMENTED_AND_ACTIVE` | 59 chunk source IDs vs 67 enabled sources |
| Safety | Post-generation and crisis branch | risk/safety agents | visible reply/interventions | yes | backend safety tests | no | `PARTIALLY_IMPLEMENTED` | rule calibration and LLM review not wired |
| Evaluation Center | Run/compare/review | evaluation router/runner | `EvaluationDashboard.tsx` | yes | local runner/results | partial | `PARTIALLY_IMPLEMENTED` | official judge incomplete |
| Knowledge Review | Source/chunk review | knowledge router | `KnowledgeReview.tsx` | yes | route/code tests | partial | `IMPLEMENTED_AND_ACTIVE` | current human review rows are empty |
| RBAC | Role and permission boundary | dependencies/permissions | guards/nav | yes | RBAC tests | partial | `IMPLEMENTED_AND_ACTIVE` | deployment/rotation verification |
| Fine-tuned Model Support | SFT/runtime experiment | training artifacts only | no active switch UI | no | dataset preparation | no | `NOT_IMPLEMENTED` | runtime model not connected |
| Long-term Memory | Cross-session semantic memory | no active implementation | privacy/memory UI partial | no | memory tests only | no | `IMPLEMENTED_BUT_DISABLED` | global memory false; semantic memory absent |
| Case RAG | Case-specific retrieval | no separate active path verified | no dedicated page | no | no current runtime evidence | no | `NOT_IMPLEMENTED` | avoid expanding scope now |
