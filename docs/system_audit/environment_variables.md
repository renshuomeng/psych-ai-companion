# Environment Variables and Feature Flags

Audit date: 2026-09-07. Values below are configuration states only; secret contents are never written.

## Effective Settings

| Variable / setting | Current effective value | Classification | Impact |
|---|---|---|---|
| `APP_ENV` | `development` | OPTIONAL | Enables development docs/static behavior |
| `PUBLIC_ACCESS_ENABLED` | `false` | REQUIRED_FOR_PUBLIC_ACCESS | Public access code flow is off |
| `ENABLE_DEV_MOCK` | `false` | OPTIONAL | Real provider path is selected when needed |
| `ARK_API_KEY` | configured | `REQUIRED_FOR_CHAT` | Enables ARK counselor/vision/video provider calls |
| `DOUBAO_MODEL_ID` | configured | `REQUIRED_FOR_CHAT` | Base counselor model ID |
| `DOUBAO_VISION_MODEL_ID` | configured | `REQUIRED_FOR_MULTIMODAL` | Image model ID |
| `DOUBAO_VIDEO_MODEL_ID` | configured | `REQUIRED_FOR_MULTIMODAL` | Video model ID |
| `VOLC_SPEECH_API_KEY` | configured | `REQUIRED_FOR_MULTIMODAL` | Header path for ASR |
| `VOLC_SPEECH_APP_ID` | empty | `REQUIRED_FOR_MULTIMODAL` | Alternative ASR auth path not active |
| `VOLC_SPEECH_ACCESS_KEY` | empty | `REQUIRED_FOR_MULTIMODAL` | Alternative ASR auth path not active |
| `AUTH_JWT_SECRET` | configured | `REQUIRED_FOR_CHAT` | Stable JWT signing |
| `PUBLIC_SESSION_SECRET` | configured | `REQUIRED_FOR_PUBLIC_ACCESS` | Public session signing |
| `INITIAL_ADMIN_PASSWORD` | configured | `OPTIONAL` | Initial admin bootstrap input |
| `RAG_ENABLED` | `true` | `REQUIRED_FOR_RAG` | Enables retrieval service |
| `RAG_V1_ENABLED` | `true` | `REQUIRED_FOR_RAG` | Selects RAG V1 path |
| `RAG_V1_BM25_ENABLED` | `true` | `REQUIRED_FOR_RAG` | Enables lexical retrieval |
| `RAG_V1_DENSE_ENABLED` | `true` | `REQUIRED_FOR_RAG` | Enables dense retrieval |
| `RAG_V1_USE_FALLBACK` | `false` | `OPTIONAL` | Legacy fallback disabled |
| `RAG_INDEX_MODE` | `production` | `REQUIRED_FOR_RAG` | Effective index mode is production |
| `RAG_STAGING_MODE` | `false` | `OPTIONAL` | Staging route disabled |
| `AGENT_V2_ENABLED` | `true` | `REQUIRED_FOR_CHAT` | Enables state/strategy/router pipeline |
| `PSYCHOLOGICAL_STATE_ANALYZER_ENABLED` | `true` | `REQUIRED_FOR_CHAT` | Runs local state analyzer |
| `STRATEGY_PLANNER_ENABLED` | `true` | `REQUIRED_FOR_CHAT` | Runs strategy planner |
| `RAG_ROUTER_ENABLED` | `true` | `REQUIRED_FOR_RAG` | Runs route decision |
| `MEMORY_ENABLED` | `true` | `OPTIONAL` | Enables session memory |
| `GLOBAL_MEMORY_ACROSS_CONVERSATIONS` | `false` | `OPTIONAL` | Global memory remains disabled |
| `SAFETY_LLM_REVIEW_ENABLED` | `true` | `OPTIONAL` | Flag exists, but no active LLM review call was found |
| `EVAL_ALLOW_PAID_FULL_RUN` | `false` | `REQUIRED_FOR_EVALUATION` | Full paid evaluation is blocked |
| `EVAL_JUDGE_PROVIDER` | `heuristic_local` | `REQUIRED_FOR_EVALUATION` | Local heuristic judge selected |
| `EVAL_JUDGE_MODEL_ID` | `local_smoke_heuristic_v1` | `REQUIRED_FOR_EVALUATION` | Not an external judge model |
| `DOUBAO_INPUT_PRICE_PER_1K` | unset | `OPTIONAL` | Cost accounting cannot calculate provider cost |
| `DOUBAO_OUTPUT_PRICE_PER_1K` | unset | `OPTIONAL` | Cost accounting cannot calculate provider cost |

## Deprecated or Parallel Names

The codebase contains legacy/example names such as `ADMIN_ACCESS_CODE` in `.env.example`, legacy LLM provider settings, and older RAG settings. They are not evidence of an active current path unless imported by the effective runtime.

## Secret Handling

Only configured/unconfigured status is recorded. No API key, JWT secret, session secret, admin password, or masked value is included here.
