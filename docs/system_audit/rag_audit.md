# RAG Audit

## Active Route

RAG V1 is active with production-approved hybrid retrieval:

- `rag_enabled=true`
- `rag_v1_enabled=true`
- BM25 enabled
- dense retrieval enabled
- fallback disabled
- production index mode
- local embedding model `BAAI/bge-m3`

The Agent V2 router can skip retrieval for safety, clarification, or purely supportive replies. High-risk and medium-risk routes are intentionally excluded from ordinary knowledge retrieval.

## Current Registry and Index Evidence

The structured registry is `care_psy_knowledge_base_v2`, version 2, with 67 enabled sources and 13,166 registry chunks. Review state counts are 1,648 pending, 6,631 approved, and 4,887 rejected. The production eligible count is 6,631.

Production BM25 reports 6,631 documents. Production Chroma reports 6,631 vectors, with observed production collection counts including interventions 4,968, professional_knowledge 990, and helping_skills 673. Production dense counts for campus_support, evidence, governance, and safety were zero at audit time; this should be treated as coverage evidence, not silently assumed to be complete.

## Legacy Split

The SQLite legacy knowledge tables contain 20,093 chunks and 6 sources, while the current file registry contains 13,166 chunks and 67 sources. The active runtime uses RAG V1 indexes; the legacy database retrieval/vector path is retained but current fallback is disabled.

## Status

- Production-approved hybrid RAG V1: `IMPLEMENTED_AND_ACTIVE`.
- Legacy retrieval/vector path: `IMPLEMENTED_BUT_DISABLED`.
- KB review and publication workflow: `IMPLEMENTED_AND_ACTIVE`.
- Complete production coverage across all registered collections: `PARTIALLY_IMPLEMENTED`.
- Retrieval quality against official external benchmark: `NOT_IMPLEMENTED`.

## Recomputed Current Counts

The current chunk JSONL files contain 13,166 records: 6,631 approved, 1,648 pending, and 4,887 rejected. The records contain 12,088 English and 1,078 Chinese chunks, 6,954 `direct_user_support`, 1,581 `psychoeducation_only`, 2,500 `helping_skills_only`, 817 `safety_only`, 3 `evidence_only`, 968 `clinical_reference_only`, and 343 `agent_policy_only`. Current chunk files contain 59 unique source IDs and 320 document IDs; the registry configuration reports 67 enabled sources.

## Effective Runtime Answer

Ordinary user chat currently calls **RAG V1 production hybrid**, specifically BM25 production plus Chroma production, because the effective settings read from the current environment are `RAG_ENABLED=true`, `RAG_V1_ENABLED=true`, BM25=true, dense=true, `RAG_V1_USE_FALLBACK=false`, `RAG_INDEX_MODE=production`, and `RAG_STAGING_MODE=false`. It does not fall back to legacy RAG when no result is found; the route returns no-source/general-support behavior.

Production BM25 metadata reports 6,631 documents. Production dense manifest reports 6,631 vectors, BAAI/bge-m3, dimension 1024, index version `KB_V2.1_dense_production_2026-09-02T151807+0000`. The latest saved RAG V2 benchmark is separate: 162 queries executed against staging on 2026-09-02.

## Metadata Isolation

The runtime retrieval code uses `USER_FACING_COLLECTIONS` and `USER_FACING_USE_MODES`, checks ordinary risk scope, blocks diagnosis/medication/dangerous instruction terms, and passes collection/metadata filters to BM25/Chroma. Production index eligibility is based on reviewed/approved chunk files. Safety and clinical-only rows exist in the registry, but production dense collections for safety/evidence/governance/campus_support were observed at zero; this is a coverage/route-isolation issue to verify, not evidence that those rows are currently reachable by ordinary production dense retrieval.

