# Legacy and Duplicate Components

| Duplicate/legacy path | Current evidence | Runtime conclusion |
|---|---|---|
| `services/rag_service.py` RAG V1 vs `retrieval_service.py` / `vector_store_service.py` legacy | `rag_v1_enabled=true`, `rag_v1_use_fallback=false`; coordinator uses async retrieval service | RAG V1 active; legacy path retained and disabled for normal fallback |
| KB registry/index JSONL vs SQLite `knowledge_chunk` tables | Active RAG V1 loads registry/index files; SQLite still has 20,093 knowledge rows | Two data planes; provenance ambiguity remains |
| Inline `counselor_agent.SYSTEM_PROMPT` vs `backend/prompts/counselor_prompt.txt` | Counselor runtime passes inline prompt to `generate_text`; prompt file not imported by counselor | Inline prompt active; text file is not authoritative |
| `llm_service.py` legacy provider abstraction vs `services/ark_client.py` | Counselor imports `ark_client`; legacy service remains in tree | ARK client active; legacy abstraction not primary |
| Synchronous multimodal flow vs `/api/multimodal/jobs` | Main UI sends conversation message; no worker transition found | Synchronous path active; jobs API not wired to worker |
| `/api/chat` legacy/simple path vs conversation API | Frontend primary chat uses conversation client; `/api/chat` remains mounted | Both endpoints exist; one is not the main UI path |
| Dedicated STT service vs speech service inside multimodal flow | `/api/stt` placeholder; attachment processing calls `speech_service.transcribe_audio` | Attachment speech path is the relevant implementation |
| SFT artifacts vs runtime model selection | Training report exists; no `USE_FINE_TUNED_COUNSELOR` runtime switch found | Preparation exists, runtime inference absent |

## Important Dead-Code Candidates

The table identifies high-confidence non-primary paths, not files safe to delete. The audit did not delete or refactor any of them because their historical or fallback use has not been proven irrelevant.
