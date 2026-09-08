# Knowledge Base V1.1 Completion Report

Updated: 2026-08-16

## Completed

- Added staging/production index mode with `RAG_INDEX_MODE=staging|production`.
- Kept backward compatibility with `RAG_STAGING_MODE`.
- Changed dense build semantics so full eligible indexing is the default; 512-limit now requires sample mode.
- Added V1.1 metadata normalization for existing chunks.
- Added review CLI for listing, exporting, importing, approving, rejecting, and bulk source decisions.
- Added health check, embedding check, production readiness check, and Chinese retrieval benchmark scripts.
- Added manual official-source workflow for WHO/MOE failed downloads.
- Added manual campus README and official source-specific READMEs.
- Added 50-query Chinese retrieval benchmark.
- Added tests for metadata, production review gate, RRF, and BM25 compatibility.

## Current Status

- Staging is usable.
- Production is intentionally not ready.
- All 4057 RAG V1 chunks remain pending.
- Current Chroma staging index has 512 vectors from the current sampled staging rebuild.
- Dry-run says a full staging dense rebuild would index 4057 eligible chunks.

## Next Required Human Work

1. Review `backend/data/knowledge_base/reports/high_priority_review_batch.csv`.
2. Fill `decision=approved` or `decision=rejected`, plus `reviewed_by`.
3. Import it with `scripts/rag/review_chunks.py import-review`.
4. Rebuild staging first, then production after enough approved chunks exist.
5. Manually download legal WHO/MOE official files and place them under `raw/manual/official/<source_id>/`.

## Suggested Commands

```powershell
python scripts\rag\review_chunks.py export-review --topic academic_stress --limit 60 --output backend\data\knowledge_base\reports\high_priority_review_batch.csv
python scripts\rag\review_chunks.py import-review backend\data\knowledge_base\reports\high_priority_review_batch.csv --reviewed-by "your_name"
python scripts\rag\build_knowledge_base.py --mode staging --sample-mode --sample-limit 512
python scripts\rag\health_check.py
python scripts\rag\check_production_readiness.py
```

For production after approval:

```powershell
python scripts\rag\build_knowledge_base.py --mode production
```
