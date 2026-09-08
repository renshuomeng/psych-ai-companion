# Current System at a Glance

## Verdict

The project is a working development-stage AI psychological-companion system with an active text path, active risk-first routing, active Agent V2 local orchestration, active ARK counseling, and active production-approved RAG V1. It is not yet a proven production clinical system.

## Strongest Current Capabilities

- Normal text conversation is wired end to end.
- High-risk input has a deterministic safety/referral branch.
- RAG publication distinguishes approved production content from staging/pending content.
- RBAC and response sanitization are present.
- Local tests and frontend production build pass.

## Most Material Gaps

- Speech is disabled in the current environment; TTS is absent.
- Async multimodal jobs have no discovered worker and are not the primary UI path.
- LLM safety review is configured conceptually but not wired.
- Fine-tuned model artifacts are prepared but not used at runtime.
- Official benchmark and LLM-judge evidence is absent.
- JWT/session secrets are configured in the current environment, but the app is running with `APP_ENV=development`; production rotation/deployment hardening remains unverified.
- Legacy and current RAG/LLM/prompt paths coexist without one authoritative source.
- Production dense coverage is zero for several registered collections observed at audit time.

## Current Effective Runtime

- Ordinary chat: production RAG V1 hybrid, BM25 + Chroma, fallback disabled.
- KB: 13,166 chunks from current chunk files; 6,631 approved, 1,648 pending, 4,887 rejected; 12,088 English and 1,078 Chinese.
- Latest retrieval benchmark: 162-query staged run on 2026-09-02; hybrid Hit@5 0.9568 and Recall@5 0.6274.
- Auth/session/admin bootstrap settings: configured in the current environment; production rotation/deployment verification remains open.
- Audio: API key configured, but provider runtime call was intentionally not made.
- Engineering estimate: demo 82%, competition 65%, production 35%.
