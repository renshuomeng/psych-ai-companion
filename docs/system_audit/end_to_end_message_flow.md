# End-to-End Message Flow

## Normal Text Message

1. Frontend calls the conversation message endpoint.
2. The conversation service verifies ownership and `CHAT_USE`, sanitizes the payload, and loads recent messages, summary, profile, and optional check-in state.
3. The coordinator runs risk detection first, then emotion analysis.
4. Agent V2 computes psychological state with local rules, plans a response strategy, and decides whether and where to retrieve.
5. RAG V1 queries the current production-approved hybrid indexes when the strategy requests knowledge.
6. Interventions are generated from state, strategy, risk, and retrieved material.
7. Counselor builds an inline prompt containing the safety and psychological context, then calls ARK using `settings.doubao_model_id`.
8. Safety applies rule-based post-processing. The configured LLM safety review is not wired into this step.
9. User and assistant messages, memory, summaries, retrieval logs, risk state, request metrics, and assistant metadata are persisted.
10. The response is sanitized according to the caller's permissions; trace, provider, and retrieval detail are not universally exposed.

## Failure and Fallback Behavior

- Missing ARK configuration causes normal non-high-risk generation to fail unless development mock mode is enabled.
- ARK retries timeout/transport failures and 429/5xx responses three times without exponential backoff.
- High-risk messages do not depend on ARK for the crisis response.
- Multimodal attachment failures are recorded per attachment so other inputs may continue.
- Local memory and local Agent V2 rules remain available independently of LLM availability.

## Audit Status

Normal text chat: `IMPLEMENTED_AND_ACTIVE`.

End-to-end clinical quality, semantic safety review, and production observability: `PARTIALLY_IMPLEMENTED`.

## Strict 32-Step Trace for “最近压力很大，总觉得论文做不好。”

1. `frontend/src/pages/Chat.tsx` renders `MultimodalChat` with `textOnly=true`.
2. The composer state is held by `MultimodalChat.tsx` in `message`; the send handler is `send()`.
3. `send()` checks the current conversation, blocks concurrent sends, creates an optimistic user row, and preserves the typed text.
4. It calls `sendConversationMessage()` from `frontend/src/api/client.ts`.
5. That function sends `POST /api/conversations/{conversation_id}/messages` with `content`, `file_ids`, `checkin`, and `client_message_id`.
6. `backend/main.py` mounts `backend/routers/conversations.py` at `/api/conversations`.
7. `conversations.send_message()` verifies the principal and `CHAT_USE`, then calls `conversation_service.send_conversation_message()`.
8. `send_conversation_message()` loads the conversation by ID and normalized owner ID; it does not accept an arbitrary other user's conversation.
9. It validates that text or at least one file exists, then calls `process_attachments()`; text-only input produces no attachment provider call.
10. It builds a multimodal context object with transcript/OCR/media-analysis fields and calls `run_multimodal_flow()`.
11. `run_multimodal_flow()` starts with `assess_risk_sources()`; for text-only input the effective risk source is the user text.
12. `RiskAgent` is rule-based in `backend/agents/risk_agent.py`; it emits a risk dictionary with level, reason, dimensions, matched terms, and evidence. It is not an LLM call.
13. For this ordinary sentence, the expected risk path is low; no high-risk crisis branch is taken.
14. The flow persists the user turn and loads memory context through `remember_user_turn()` and `load_memory_context()`.
15. `analyze_emotion()` runs on the combined text and produces a local heuristic emotion object; face emotion is absent for text-only input.
16. `analyze_psychological_state()` in `backend/agents/psychological_state_analyzer.py` runs asynchronously with message, emotion, risk, check-in, multimodal context, and recent messages.
17. Its schema includes emotion, cause, needs, stage, information gaps, confidence, evidence, and `method=local_rules_v1`.
18. `plan_strategy()` in `backend/services/strategy_planner.py` receives the psychological state, risk, and message. It does not call an LLM.
19. Its output includes primary/secondary strategies, advice/question/RAG booleans, response constraints, reason codes, and confidence.
20. `route_rag()` in `backend/services/rag_router.py` receives message, state, strategy, and risk. It is rule-based and hard-coded lexicon logic, not an LLM router.
21. For thesis/academic pressure, the router normally requests retrieval and selects interventions/professional_knowledge/campus_support; for low-confidence or safety routes it can skip retrieval.
22. The generated query combines the original message with cause, emotion, strategy, state needs, and topic lexicon expansions.
23. `retrieve_context_async()` receives the route query, route `top_k` (normally 3), metadata filter, psychological context, and collection list.
24. `rag_service.py` selects RAG V1 because current effective settings are RAG enabled, V1 enabled, fallback disabled, production index mode.
25. RAG V1 combines BM25 and dense Chroma retrieval, then reranks/fuses results. Production indexes are 6,631 eligible approved chunks; the saved benchmark's staging run used `top_k=5`.
26. The RAG V1 code enforces user-facing collections/use modes and rejects diagnosis, medication, dangerous-instruction, and safety-sensitive ordinary retrieval paths. Returned documents carry metadata such as `user_facing`, `clinical_only`, `risk_scope`, `use_mode`, and review status.
27. Up to the route's result limit, returned documents are passed as `knowledge_context` and `knowledge_sources` to the coordinator.
28. `generate_counseling_reply()` receives message, emotion, risk, interventions, memory, recent messages, evidence, psychological state, strategy plan, RAG route, and knowledge context.
29. `build_context_bundle()` packages current message, risk, memory, recent messages, RAG context, multimodal context, and evidence; the prompt builder also serializes state/strategy/route and up to three source briefs.
30. `backend/agents/counselor_agent.py` calls `services.ark_client.generate_text()`, which posts to ARK `/responses` using `settings.doubao_model_id`. The inline `SYSTEM_PROMPT` is active; `prompts/counselor_prompt.txt` is not imported here.
31. The reply is cleaned, then `review_response()` in `backend/agents/safety_agent.py` runs after generation. It can enforce crisis referral, replace unsafe wording with a safe fallback, or pass the reply. Provider failure is surfaced as an `AppError` after ARK retries; it is not silently converted to a normal answer.
32. The coordinator persists the assistant turn, request metrics, risk state, retrieval log, memory/summary updates, and metadata. The conversation service returns `conversation`, `user_message`, `assistant_message`, attachment/transcript/media fields, and analysis metadata; `MultimodalChat` replaces the optimistic row and renders the assistant message.

## Prompt Inputs Confirmed

The active counselor prompt includes conversation memory/history when supplied, psychological state, strategy, risk, RAG route/context, interventions, check-in, multimodal context, evidence, and citation source briefs. The active base model is the configured `DOUBAO_MODEL_ID`; no fine-tuned runtime switch was found.

