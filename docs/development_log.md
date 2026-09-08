# CARE-Psy Development Log

## 2026-08-10 Phase 0-3 Implementation

### Completed

- Phase 0: Added `docs/current_system_audit.md` and `docs/current_architecture.md` based on the actual repository.
- Phase 1: Added cause and strategy benchmark datasets, safety redteam dataset, CARE-Psy `rag_cases.jsonl`, and runnable evaluation runners.
- Phase 1: Added `evaluate_strategy.py`, `evaluate_cause.py`, `evaluate_safety_redteam.py`, and `evaluate_baseline.py`.
- Phase 2: Expanded knowledge base ingestion to support JSON documents and CARE-Psy taxonomy directories.
- Phase 2: Added psychological metadata fields: `reviewed`, `usage_note`, `emotion`, `cause`, `strategy`, `risk_level`, and `intervention`.
- Phase 3: Added `BM25_only` alias, emotion-aware hybrid retrieval modes, configurable retrieval weights, NDCG metrics, and manual RAG debugging options.
- Safety: Added simple English high-risk phrase detection for redteam coverage.

### Explicitly Skipped

- Ablation experiments are not run in this round per user request.
- Doubao direct-response baseline batch evaluation is scaffolded but skipped by default to avoid unapproved API cost and inconsistent prompting.

### Pending Or Needs External Input

- ChromaDB is not active in the current Python environment. The system currently uses SQLite + deterministic local embeddings. To switch to ChromaDB, install a compatible `chromadb` package and add a provider implementation.
- Fine-tuning, SFT, DPO, and specialist model training require licensed datasets, training hardware or a managed platform, and an approved evaluation protocol.
- Professional psychological knowledge sources remain `source_unverified`; they need review by qualified people before real deployment.

## 2026-08-11 Multi-Conversation Chat Upgrade

### Completed

- Added `Conversation` as the business-level chat container while preserving `conversation_id == session_id` compatibility.
- Added `/api/conversations` CRUD APIs and conversation-based message sending.
- Added message persistence fields: `conversation_id`, `sequence`, `message_type`, and `attachments_json`.
- Added attachment ownership fields: `conversation_id` and `message_id`.
- Rebuilt the main chat UI with a conversation sidebar, message history restore, URL restore at `/chat/{conversation_id}`, rename, delete, and mobile drawer.
- Moved analysis details behind a collapsible section while preserving Emotion, Risk, Intervention, Evidence, RAG sources, Memory, metrics, and Agent Trace.
- Added `scripts/migrate_conversations.py` with SQLite backup before migration.

### Notes

- The old `/api/chat` and `/api/chat/multimodal` endpoints remain for compatibility, but the new frontend uses conversation-based APIs.
- Default cross-conversation memory sharing remains disabled.

## 2026-08-11 Psychological RAG Knowledge Base V1

### Completed

- Added the registry-controlled offline RAG V1 pipeline based on `knowledge_sources_v1.yaml`.
- Added strict allowlist validation, redirect-domain checks, SHA256 manifest records, duplicate detection, and safe ZIP extraction.
- Added HTML/PDF/DOCX/TXT/Markdown/JSON/JSONL parsing, source-faithful cleaning, configurable chunking, chunk review CSVs, and smoke query reports.
- Added BGE-M3 based RAG V1 embedding support with an explicit no-fake-embedding failure path.
- Added Chroma staging collections and a BM25 index under `backend/data/knowledge_base/indexes/`.
- Kept RAG V1 offline: it is not connected to chat APIs, conversation APIs, frontend chat, or any Agent.
- Updated the old SQLite knowledge ingestion to ignore RAG V1 generated directories so chat retrieval stays on the existing seed knowledge until a later integration phase.

### Run Results

- Registry sources: 24.
- Download: 14 successful, 1 partial, 9 failed due robots.txt or redirect-domain restrictions.
- Parsed documents: 179.
- Chunks: 4057, all pending review.
- BM25: full index over 4057 chunks.
- Chroma: staging collections created; 512 chunks embedded with BGE-M3 for partial dense staging.
- Smoke queries: 10/10 returned dense results; BM25 returned no result for Chinese queries because current downloaded content is English and this phase does not implement query rewrite or translation.

### Pending Or Needs External Input

- WHO and MOE sources were not downloaded because the strict robots.txt check disallowed fetching those official pages.
- NHS Thought Record attachment redirected to `assets.nhs.uk`, which was not in the registry `allowed_domains`, so the attachment was rejected.
- Safety, governance, campus, evidence, and helping-skills Chroma collections exist but are empty until allowed sources are downloadable or manually supplied.
- Full BGE-M3 embedding of all 4057 chunks is possible but slow on CPU; current default indexes the first 512 chunks for dense staging and indexes all chunks with BM25.

## 2026-08-13 RAG V1 Chat Integration

### Completed

- Connected RAG V1 to the formal chat path through `services.rag_service.retrieve_context_async`.
- Added `rag_v1_hybrid_bilingual` retrieval: BM25 over all chunks, optional Chroma dense retrieval, bilingual Chinese-to-English query expansion, deduplication, and reranking.
- Kept the old SQLite demo RAG as fallback when the V1 index is missing or insufficient.
- Added citation-ready `knowledge_sources` fields: `citation_label`, organization, year, official URL, section, score, and preview.
- Updated `CounselorAgent` prompting so model replies can cite retrieved sources as `（来源1）` / `（来源2）` without inventing references.
- Updated the frontend Knowledge Sources card to display source labels, organization/year/section, relevance, review status, and official links.
- Added integration tests for Chinese bilingual query expansion and chat retrieval.

### Notes

- Chinese retrieval currently uses a controlled lexicon-based bilingual expansion, not an online translation model. It covers thesis/study stress, career anxiety, sleep, relationships, loneliness, anxiety, low mood, perfectionism, and emotion regulation.
- First retrieval after backend start may be slow because BGE-M3 is loaded from local cache.
- RAG V1 chunks remain `pending` review, so UI still marks most sources as pending even when they are from official/public institutions.

## 2026-08-16 Agent V2: Psychological State, Strategy Planner and RAG Router

### Completed

- Added `PsychologicalStateAnalyzer` with structured emotion, cause, needs, dialogue stage, confidence, uncertainty and evidence fields.
- Added local `StrategyPlanner` to decide whether the next reply should validate, clarify, ask a question, provide information or give problem-solving support.
- Added `RAGRouter` to decide whether to retrieve knowledge, which V1 collections to use, how to rewrite the routed query and what metadata filters to apply.
- Integrated Agent V2 into `/api/chat`, `/api/chat/multimodal` and conversation-based chat while preserving high-risk crisis routing before ordinary counseling.
- Refactored `CounselorAgent` so it can follow `strategy_plan` and consume pre-routed RAG context instead of always deciding retrieval internally.
- Extended RAG V1 retrieval with collection filters, topic filters and `RAG_STAGING_MODE`.
- Added frontend analysis display for psychological state, support strategy and RAG route.
- Added Agent V2 evaluation fixtures and unit tests.

### Notes

- `PsychologicalStateAnalyzer` is deterministic local rules in this version for stability and repeatable tests. It can later be replaced or refined by one structured Doubao call behind the same schema.
- Ordinary RAG is skipped for high-risk and medium-risk safety-monitoring turns; safety handling remains controlled by `RiskAgent` and `SafetyAgent`.

### Pending Or Needs External Input

- Production use should require human-reviewed V1 chunks by setting `RAG_STAGING_MODE=false` after chunk review.
- Professional validation is needed for cause/need/stage taxonomy thresholds before real deployment.
- Fine-tuning and dataset construction remain future work because they require licensed data, annotation standards and a separate evaluation protocol.
