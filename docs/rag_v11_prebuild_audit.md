# CARE-Psy RAG V1.1 Prebuild Audit

Updated: 2026-08-16

## Scope

This audit covers only the Knowledge Base V1.1 work: corpus governance, lifecycle status, staging/production separation, review workflow, index health, retrieval evaluation, and legacy KB migration risk.

It intentionally does not change PsychologicalStateAnalyzer, StrategyPlanner, Case RAG, fine-tuning, long-term memory, CriticAgent, or frontend layout.

## Current Inventory

| Item | Current value |
|---|---:|
| Registry sources | 24 |
| Auto-download sources | 24 |
| Download success | 14 |
| Download partial | 1 |
| Download failed | 9 |
| Documents discovered | 265 |
| Parsed documents | 179 |
| Pending chunks | 4057 |
| Approved chunks | 0 |
| Rejected chunks | 0 |
| Languages | en: 4057 |
| BM25 staging docs | 4057 |
| BM25 production docs | 0 |
| Chroma staging vectors | 512 |
| Chroma production vectors | 0 |

## Collections

| Collection | Chunks | Status |
|---|---:|---|
| interventions | 4044 | present |
| professional_knowledge | 13 | present |
| campus_support | 0 | empty |
| safety | 0 | empty |
| helping_skills | 0 | empty |
| governance | 0 | empty |
| evidence | 0 | empty |
| case_rag | 0 | reserved / separate |

## Lifecycle Status

V1.1 lifecycle now uses:

```text
RAW -> PARSED -> CLEANED -> CHUNKED -> PENDING -> REVIEW -> APPROVED/REJECTED -> PRODUCTION INDEX
```

Current state:

- `backend/data/knowledge_base/chunks/pending/chunks.jsonl`: 4057 chunks
- `backend/data/knowledge_base/chunks/approved/chunks.jsonl`: 0 chunks
- `backend/data/knowledge_base/chunks/rejected/chunks.jsonl`: 0 chunks
- all existing chunks have been normalized with V1.1 metadata fields.

## Index Boundary

New runtime/build setting:

```env
RAG_INDEX_MODE=staging
```

Rules:

- `staging`: pending + approved chunks may be used; rejected chunks are excluded.
- `production`: only approved/reviewed chunks may be used.
- `RAG_STAGING_MODE` is retained for backward compatibility.

Dense build limit was corrected:

- Old behavior: `RAG_V1_MAX_DENSE_CHUNKS=512` silently limited dense indexing by default.
- New behavior: full eligible dense indexing is the default.
- Sampling now requires `RAG_BUILD_SAMPLE_MODE=true` or `--sample-mode`.

Current dry-run result: staging would index 4057 eligible dense chunks. The existing Chroma index still has 512 vectors because a full dense rebuild was not run in this pass.

## Manual Source Workflow

Automatic download failed for these official sources, mostly because robots.txt blocked fetching:

- `WHO_SELFHELP_2026`
- `WHO_DWM_STRESS_2020`
- `WHO_HELPING_SKILLS_2025`
- `WHO_PSYCH_IMPLEMENTATION_2024`
- `WHO_MHGAP_2023`
- `WHO_SAFETY_PLANNING_2023`
- `WHO_LIVE_LIFE_2021`
- `MOE_HIGHER_ED_MH_GUIDE_2018`
- `MOE_STUDENT_MH_ACTION_2023_2025`

Manual drop zones were added under:

```text
backend/data/knowledge_base/raw/manual/official/<source_id>/
backend/data/knowledge_base/raw/manual/campus/
```

The pipeline now recognizes `raw/manual/official/<source_id>/` and reuses the registry metadata for manually supplied official files.

## Review Workflow

Added:

```text
scripts/rag/review_chunks.py
```

Supported commands:

- `list`
- `export-review`
- `import-review`
- `approve`
- `reject`
- `bulk-approve-source`
- `bulk-reject-source`

Generated first high-priority batch:

```text
backend/data/knowledge_base/reports/high_priority_review_batch.csv
```

This batch contains 60 pending academic-stress chunks for human review.

## Health And Evaluation

Generated reports:

```text
backend/data/knowledge_base/reports/knowledge_base_v11_report.md
backend/data/knowledge_base/reports/knowledge_base_v11_report.json
backend/data/knowledge_base/reports/source_balance_report.csv
backend/data/knowledge_base/reports/chunk_quality_report.csv
backend/data/knowledge_base/reports/dedup_report.json
backend/data/knowledge_base/reports/embedding_health.json
backend/data/knowledge_base/reports/rag_v11_benchmark.json
```

Quick retrieval benchmark on 20 Chinese queries:

| Mode | Hit@5 | MRR | NDCG@5 | No-result |
|---|---:|---:|---:|---:|
| BM25 | 0.45 | 0.4167 | 0.4234 | 0.30 |
| Dense | 0.40 | 0.4000 | 0.3866 | 0.00 |
| Hybrid | 0.55 | 0.4583 | 0.4890 | 0.00 |

Hybrid is currently best, but Chinese retrieval still needs more Chinese corpus and better query expansion.

## Production Readiness

```text
STAGING_READY=true
PRODUCTION_READY=false
```

Production blockers:

- no approved chunks
- approved core topic coverage is 0%
- production BM25 index is empty

## Files Modified Or Added

- `backend/config.py`
- `.env.example`
- `backend/services/knowledge_source_registry.py`
- `backend/services/rag_v1_index_service.py`
- `backend/services/rag_v1_pipeline.py`
- `backend/services/rag_v1_retrieval_service.py`
- `backend/data/knowledge_base/sources/knowledge_sources_v1.yaml`
- `scripts/rag/kb_v11_utils.py`
- `scripts/rag/review_chunks.py`
- `scripts/rag/health_check.py`
- `scripts/rag/check_embeddings.py`
- `scripts/rag/check_production_readiness.py`
- `scripts/rag/normalize_chunks_v11.py`
- `scripts/rag/run_retrieval_benchmark.py`
- `evaluation/rag_v11/retrieval_queries.jsonl`
- `backend/tests/test_rag_v11.py`
- manual source README files under `backend/data/knowledge_base/raw/manual/`

## Known Gaps

- No chunk has been manually approved yet.
- WHO/MOE sources still need manual legal download by the project owner.
- Chroma staging still contains 512 vectors until a full staging rebuild is run.
- Safety, campus, helping-skills, governance, and evidence collections are still empty.
- Legacy KB remains available as fallback and should be reviewed or disabled before a strict public demo.
