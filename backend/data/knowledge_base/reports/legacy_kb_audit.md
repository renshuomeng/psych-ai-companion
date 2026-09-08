# Legacy KB Audit

Updated: 2026-08-16

## Current Legacy Resources

Legacy KB exists in:

```text
backend/data/knowledge_base.json
backend/data/knowledge_base/manifests/seed_sources.jsonl
backend/data/knowledge_base/raw/*.md
backend/database/psych_ai.sqlite
```

Current SQLite inventory:

- 5 knowledge sources
- 15 knowledge chunks
- 15 FTS rows

The legacy records are Chinese demo/self-help seed content and are marked `source_unverified` / `reviewed=false`.

## Recommendation

| Source | Recommendation |
|---|---|
| `kb_study_001` | MIGRATE after human review; useful for Chinese academic-stress fallback. |
| `kb_sleep_001` | MIGRATE after human review; useful while Chinese sleep corpus is thin. |
| `kb_job_001` | KEEP as fallback until career-anxiety corpus is added. |
| `kb_relationship_001` | KEEP as fallback until campus/relationship Chinese sources are added. |
| `kb_crisis_001` | DO NOT use as ordinary RAG citation; keep crisis wording governed by RiskAgent/SafetyAgent. |

## Migration Plan

1. Export selected legacy chunks to a review CSV.
2. Human-review wording, source attribution, and safety boundaries.
3. Convert approved content into manual campus Markdown cards.
4. Rebuild staging.
5. Approve only reviewed chunks.
6. Set `RAG_V1_USE_FALLBACK=false` when production coverage is sufficient.

Do not delete the legacy KB yet. It is still useful for prototype fallback and Chinese demo continuity.
