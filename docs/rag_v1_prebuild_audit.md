# RAG V1 Prebuild Audit

Date: 2026-08-11

## Scope

This upgrade only builds the offline Psychological RAG Knowledge Base V1 pipeline:

- source registry ingestion
- official allowlist downloader
- parsing, cleaning and chunking
- chunk review preparation
- real embedding path for RAG V1
- Chroma staging indexes
- BM25 indexes
- smoke retrieval scripts and reports

It intentionally does not modify chat APIs, frontend chat pages, CounselorAgent, EmotionAgent, RiskAgent, SafetyAgent, MultimodalAgent, model fine-tuning, Case RAG, reranking, query rewriting or chat integration.

## Existing RAG

The project already had a lightweight RAG path:

- `backend/services/rag_service.py`
- `backend/services/retrieval_service.py`
- `backend/services/vector_store_service.py`
- `backend/services/knowledge_ingestion_service.py`
- `backend/services/document_parser_service.py`
- `backend/services/chunking_service.py`
- `backend/data/knowledge_base/raw/*.md`
- SQLite `knowledge_source`, `knowledge_chunk` and FTS-backed keyword search

## Existing Embedding

The existing runtime embedding provider is `LocalHashingEmbeddingProvider`, configured by:

- `EMBEDDING_PROVIDER=local`
- `EMBEDDING_MODEL=local-hashing-v1`

That provider is retained for the old demo path, but it is not used as a fake embedding fallback for RAG V1. RAG V1 adds a separate real embedding path:

- `RAG_EMBEDDING_PROVIDER=local`
- `RAG_EMBEDDING_MODEL=BAAI/bge-m3`

If `sentence-transformers` or the model cannot load, RAG V1 reports `embedding_model_download_failed` and keeps download/parse/clean/chunk results.

## Existing Chroma

The previous project had a configurable `CHROMA_PERSIST_DIR`, but the active vector code stored embeddings in SQLite. RAG V1 adds actual Chroma staging index construction under:

`backend/data/knowledge_base/indexes/chroma/`

## Existing Dependencies

Already present before this work:

- FastAPI, SQLAlchemy, httpx, Pillow, pytest, pydantic
- PyYAML and requests were available in the active Python environment

Added for RAG V1:

- beautifulsoup4
- pypdf
- rank-bm25
- jieba
- chromadb
- sentence-transformers

## New Files

- `backend/services/knowledge_source_registry.py`
- `backend/services/knowledge_download_service.py`
- `backend/services/knowledge_cleaning_service.py`
- `backend/services/rag_v1_index_service.py`
- `backend/services/rag_v1_pipeline.py`
- `scripts/rag/download_sources.py`
- `scripts/rag/build_knowledge_base.py`
- `scripts/rag/test_retrieval.py`
- `evaluation/rag_v1_smoke_queries.json`
- `backend/data/knowledge_base/sources/knowledge_sources_v1.yaml`
- `docs/rag_v1_prebuild_audit.md`

## Modified Files

- `backend/config.py`
- `backend/services/document_parser_service.py`
- `backend/services/embedding_service.py`
- `.env.example`
- `.gitignore`
- `backend/requirements.txt`
- `README.md`

## Data Safety

The downloader only uses sources with `enabled=true` and `auto_download=true` in the registry. It checks final redirect domains against `allowed_domains`, does not search for alternatives, records failures, computes SHA256, and keeps manual case data reserved for future Case RAG.
