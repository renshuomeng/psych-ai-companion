# Agent V2 Prebuild Audit

Date: 2026-08-16

## Existing Reusable Modules

- `RiskAgent` already detects self-harm, suicide, harm-to-others, negated risk and reported/quoted risk contexts.
- `EmotionAgent` already outputs category plus dimensional values: valence, arousal, control and intensity.
- RAG V1 already provides BM25 + optional Chroma staging retrieval, bilingual lexicon query expansion and citation-ready source metadata.
- `CounselorAgent` already calls Volcengine Ark / Doubao and returns provider metadata.
- Conversation storage already persists assistant metadata, evidence, retrieval result, request metrics and agent trace.

## Main Gaps Before This Phase

- The system did not have a separate psychological state hypothesis layer. Emotion, cause, user needs and dialogue stage were mixed into older retrieval context.
- RAG retrieval happened inside `CounselorAgent`, so the system could not explicitly explain why it retrieved or skipped knowledge.
- Strategy selection was implicit. The model could give advice even when the better next move was validation or clarification.
- Frontend analysis did not expose psychological state, strategy planning or RAG routing.

## This Phase Scope

- Add `PsychologicalStateAnalyzer`.
- Add local `StrategyPlanner`.
- Add `RAGRouter` that reuses the existing V1 knowledge base.
- Keep high-risk crisis handling before ordinary psychological state and RAG flow.
- Integrate Agent V2 outputs into `CounselorAgent`, conversation metadata, trace, metrics and frontend analysis.

## Explicitly Out Of Scope

- No ablation experiments.
- No fine-tuning, SFT, DPO or specialist model training.
- No new vector database or duplicate knowledge base.
- No long-term memory redesign, case RAG or CriticAgent.

## Compatibility Notes

- `AGENT_V2_ENABLED=false` keeps the old counselor-side retrieval path available.
- `RAG_STAGING_MODE=true` allows current pending V1 chunks to be used for development demos. Production should switch this to `false` after human review marks chunks `approved` or `reviewed`.
- The first version of `PsychologicalStateAnalyzer` uses deterministic local rules for stability and testability. It can later be upgraded to one structured Doubao call behind the same schema without changing downstream modules.
