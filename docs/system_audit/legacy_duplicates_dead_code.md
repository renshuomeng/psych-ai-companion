# Legacy, Duplicate, and Dead-Code Risk

## Observed Parallel Implementations

- RAG V1 production indexes are active; legacy `retrieval_service.py` and `vector_store_service.py` remain as fallback/older paths.
- Active ARK counselor generation coexists with legacy `llm_service.py` abstractions for mock/Ollama/Qwen-style providers.
- The structured KB registry/index data plane coexists with legacy SQLite knowledge tables.
- A dedicated STT router/service coexists with the active speech service used by multimodal flow, but the dedicated endpoint remains placeholder-level.
- Async multimodal job APIs coexist with synchronous attachment processing in the primary frontend flow.
- The prompt text file coexists with the inline counselor prompt.

## Risk

These are not automatically removable dead code. They create ambiguity over which path is authoritative, increase test surface, and make deployment/configuration drift more likely. The audit did not delete or refactor them.

## Status

Legacy implementations retained but disabled/not primary: `IMPLEMENTED_BUT_DISABLED`.

Source-of-truth consolidation: `NOT_IMPLEMENTED`.


