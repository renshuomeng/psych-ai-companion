from typing import Any
import time

from agents.counselor_agent import generate_counseling_reply
from agents.emotion_agent import analyze_emotion, infer_visual_emotion
from agents.intervention_agent import recommend_interventions
from agents.memory_agent import load_memory_context, remember_assistant_turn, remember_user_turn
from agents.psychological_state_analyzer import analyze_psychological_state
from agents.risk_agent import assess_risk, assess_risk_sources
from agents.safety_agent import CRISIS_REFERRAL_REPLY, review_response, review_response_async
from config import get_settings
from database.db import SessionLocal, init_db
from services.evidence_service import build_evidence_objects, split_emotion_evidence
from services.metrics_service import record_request_metric
from services.rag_router import route_rag
from services.rag_service import retrieve_context_async
from services.strategy_planner import plan_strategy


def _string_trace_to_structured(trace: list[str]) -> list[dict[str, str]]:
    structured = []
    for item in trace:
        agent, _, summary = item.partition(":")
        structured.append(
            {
                "agent": agent.strip() or "Agent",
                "status": "completed",
                "summary": summary.strip() or item,
            }
        )
    return structured


def _safety_trace_to_structured(trace: list[Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in trace:
        if not isinstance(item, str):
            continue
        if not (item.startswith("LLMSafetyAgent") or item.startswith("SafetyAgent")):
            continue
        agent, _, summary = item.partition(":")
        output.append(
            {
                "agent": agent.strip() or "SafetyAgent",
                "status": "fallback" if "fallback" in summary else "completed",
                "summary": summary.strip() or item,
            }
        )
    return output


def _psychological_context_for_rag(
    psychological_state: dict[str, Any],
    strategy_plan: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    emotion = psychological_state.get("emotion") or {}
    cause = psychological_state.get("cause") or {}
    return {
        "emotion": emotion.get("primary", "unknown"),
        "cause": cause.get("category", "unknown"),
        "strategy": strategy_plan.get("primary_strategy", "supportive_presence"),
        "risk_level": risk.get("level", "low"),
    }


async def _prepare_agent_v2(
    *,
    message: str,
    emotion: dict[str, Any],
    risk: dict[str, Any],
    checkin: dict[str, Any] | None = None,
    multimodal_context: dict[str, Any] | None = None,
    session_id: str = "",
    recent_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.agent_v2_enabled:
        return {
            "enabled": False,
            "psychological_state": {},
            "strategy_plan": {},
            "rag_route": {},
            "knowledge_context": None,
            "knowledge_sources": [],
            "agent_trace": [],
            "stages": {},
            "provider_calls": 0,
        }

    stages: dict[str, int] = {}
    agent_trace: list[dict[str, str]] = []
    psychological_state: dict[str, Any] = {}
    strategy_plan: dict[str, Any] = {}
    rag_route: dict[str, Any] = {}
    knowledge_context: dict[str, Any] | None = None

    try:
        started = time.perf_counter()
        psychological_state = await analyze_psychological_state(
            message,
            emotion=emotion,
            risk=risk,
            checkin=checkin,
            multimodal_context=multimodal_context,
            recent_messages=recent_messages,
        )
        stages["psych_state_ms"] = int((time.perf_counter() - started) * 1000)
        agent_trace.append(
            {
                "agent": "PsychologicalStateAnalyzer",
                "status": "completed",
                "summary": (
                    f"{(psychological_state.get('emotion') or {}).get('primary', 'unknown')} / "
                    f"{(psychological_state.get('cause') or {}).get('category', 'unknown')}，"
                    f"置信度 {psychological_state.get('confidence', 0)}"
                ),
            }
        )
    except Exception as exc:
        agent_trace.append(
            {
                "agent": "PsychologicalStateAnalyzer",
                "status": "fallback",
                "summary": f"心理状态分析失败，回退旧版流程：{type(exc).__name__}",
            }
        )
        return {
            "enabled": True,
            "psychological_state": {},
            "strategy_plan": {},
            "rag_route": {},
            "knowledge_context": None,
            "knowledge_sources": [],
            "agent_trace": agent_trace,
            "stages": stages,
            "provider_calls": 0,
        }

    try:
        started = time.perf_counter()
        strategy_plan = plan_strategy(psychological_state, risk=risk, message=message)
        stages["strategy_ms"] = int((time.perf_counter() - started) * 1000)
        agent_trace.append(
            {
                "agent": "StrategyPlanner",
                "status": "completed",
                "summary": (
                    f"{strategy_plan.get('primary_strategy', 'supportive_presence')}；"
                    f"建议={strategy_plan.get('should_give_advice')}，RAG={strategy_plan.get('should_use_rag')}"
                ),
            }
        )
    except Exception as exc:
        strategy_plan = {
            "primary_strategy": "supportive_presence",
            "secondary_strategy": ["emotional_validation"],
            "should_give_advice": False,
            "should_ask_question": True,
            "should_use_rag": False,
            "reason_codes": ["strategy_planner_failed"],
        }
        agent_trace.append(
            {
                "agent": "StrategyPlanner",
                "status": "fallback",
                "summary": f"策略规划失败，使用支持性陪伴：{type(exc).__name__}",
            }
        )

    try:
        started = time.perf_counter()
        rag_route = route_rag(
            message=message,
            psychological_state=psychological_state,
            strategy_plan=strategy_plan,
            risk=risk,
        )
        stages["rag_routing_ms"] = int((time.perf_counter() - started) * 1000)
        agent_trace.append(
            {
                "agent": "RAGRouter",
                "status": "completed",
                "summary": (
                    "需要检索" if rag_route.get("should_retrieve") else f"跳过检索：{rag_route.get('fallback', 'no_rag')}"
                ),
            }
        )
    except Exception as exc:
        rag_route = {
            "should_retrieve": False,
            "collections": [],
            "query": message,
            "metadata_filter": {},
            "top_k": 3,
            "reason_codes": ["rag_router_failed"],
            "fallback": "legacy_rag_or_no_rag",
        }
        agent_trace.append(
            {
                "agent": "RAGRouter",
                "status": "fallback",
                "summary": f"RAG 路由失败，暂不检索：{type(exc).__name__}",
            }
        )

    if rag_route.get("should_retrieve"):
        try:
            started = time.perf_counter()
            knowledge_context = await retrieve_context_async(
                rag_route.get("query") or message,
                top_k=int(rag_route.get("top_k") or 3),
                session_id=session_id,
                metadata_filter=rag_route.get("metadata_filter") or None,
                psychological_context=_psychological_context_for_rag(psychological_state, strategy_plan, risk),
                collections=rag_route.get("collections") or None,
            )
            stages["retrieval_ms"] = int((time.perf_counter() - started) * 1000)
            agent_trace.append(
                {
                    "agent": "RetrievalAgent",
                    "status": "completed",
                    "summary": (
                        f"{knowledge_context.get('retrieval_status', 'unknown')}，"
                        f"来源 {len(knowledge_context.get('documents', []))} 条"
                    ),
                }
            )
        except Exception as exc:
            stages["retrieval_ms"] = int((time.perf_counter() - started) * 1000)
            knowledge_context = {
                "query": rag_route.get("query") or message,
                "retrieved_chunks": [],
                "documents": [],
                "retrieval_status": "retrieval_failed",
                "retrieval_mode": "agent_v2_routed_rag",
                "error": type(exc).__name__,
                "rag_route": rag_route,
            }
            agent_trace.append(
                {
                    "agent": "RetrievalAgent",
                    "status": "fallback",
                    "summary": f"检索失败，本轮不引用来源：{type(exc).__name__}",
                }
            )
    else:
        knowledge_context = {
            "query": rag_route.get("query") or message,
            "retrieved_chunks": [],
            "documents": [],
            "retrieval_status": "skipped_by_rag_router",
            "retrieval_mode": "agent_v2_routed_rag",
            "rag_route": rag_route,
        }

    return {
        "enabled": True,
        "psychological_state": psychological_state,
        "strategy_plan": strategy_plan,
        "rag_route": rag_route,
        "knowledge_context": knowledge_context,
        "knowledge_sources": (knowledge_context or {}).get("documents", []),
        "agent_trace": agent_trace,
        "stages": stages,
        "provider_calls": 0,
    }


async def run_chat_flow(
    message: str,
    checkin: dict[str, Any] | None = None,
    face_emotion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_trace: list[str] = []

    risk = assess_risk(message)
    agent_trace.append(f"RiskAgent: {risk['level']} risk")

    emotion = analyze_emotion(message, checkin=checkin, face_emotion=face_emotion)
    agent_trace.append(
        f"EmotionAgent: detected {emotion['label']} with intensity {emotion['intensity']}"
    )

    if risk["level"] == "high":
        result = {
            "emotion": emotion,
            "risk": risk,
            "reply": CRISIS_REFERRAL_REPLY,
            "interventions": [
                {
                    "type": "crisis_referral",
                    "title": "危机转介优先",
                    "description": "停止普通疏导，优先联系可信任的人、学校辅导员、急救电话或危机干预热线。",
                }
            ],
            "agent_trace": [
                *agent_trace,
                "CoordinatorAgent: high risk detected, skipped CounselorAgent",
            ],
        }
        return review_response(result)

    agent_v2 = await _prepare_agent_v2(
        message=message,
        emotion=emotion,
        risk=risk,
        checkin=checkin,
    )
    agent_trace.extend(
        f"{item['agent']}: {item['summary']}"
        for item in agent_v2.get("agent_trace", [])
        if isinstance(item, dict)
    )

    interventions = recommend_interventions(
        emotion,
        checkin=checkin,
        risk=risk,
        knowledge_sources=agent_v2.get("knowledge_sources", []),
    )
    agent_trace.append(
        f"InterventionAgent: recommended {len(interventions)} intervention(s)"
    )

    reply, provider_result, knowledge_sources, generation_metadata = await generate_counseling_reply(
        message=message,
        emotion=emotion,
        risk=risk,
        interventions=interventions,
        checkin=checkin,
        psychological_state=agent_v2.get("psychological_state") or None,
        strategy_plan=agent_v2.get("strategy_plan") or None,
        rag_route=agent_v2.get("rag_route") or None,
        knowledge_context=agent_v2.get("knowledge_context"),
    )
    agent_trace.append("CounselorAgent: called volcengine doubao model")

    result = {
        "emotion": emotion,
        "risk": risk,
        "reply": reply,
        "interventions": interventions,
        "agent_trace": agent_trace,
        "provider_metadata": {
            **provider_result.as_metadata(),
            "provider_calls": 1 + int(agent_v2.get("provider_calls", 0) or 0),
            **generation_metadata,
        },
        "knowledge_sources": knowledge_sources,
        "psychological_state": agent_v2.get("psychological_state", {}),
        "strategy_plan": agent_v2.get("strategy_plan", {}),
        "rag_route": agent_v2.get("rag_route", {}),
        "retrieval": generation_metadata.get("retrieval", {}),
    }

    return await review_response_async(result)


async def run_multimodal_flow(
    session_id: str,
    message: str,
    checkin: dict[str, Any] | None,
    multimodal_context: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    init_db()
    agent_trace: list[dict[str, str]] = [
        {
            "agent": "MultimodalAgent",
            "status": "completed",
            "summary": "已汇总文字、转写、OCR 和媒体分析结果",
        }
    ]

    risk_sources = {
        "user_text": message,
        "audio_transcript": multimodal_context.get("audio_transcript", ""),
        "video_transcript": multimodal_context.get("video_transcript", ""),
        "image_ocr": "\n".join(multimodal_context.get("image_ocr", [])),
        "video_ocr": "\n".join(multimodal_context.get("video_ocr", [])),
    }
    combined_text = "\n".join(text for text in risk_sources.values() if text)
    risk = assess_risk_sources(risk_sources)
    agent_trace.append(
        {
            "agent": "RiskAgent",
            "status": "completed",
            "summary": f"风险等级 {risk['level']}",
        }
    )
    evidence_objects = build_evidence_objects(message, checkin, multimodal_context, risk=risk)
    agent_trace.append(
        {
            "agent": "EvidenceBuilder",
            "status": "completed",
            "summary": f"生成 {len(evidence_objects)} 条统一证据对象",
        }
    )

    with SessionLocal() as db:
        user_memory_text = message or combined_text
        attachment_items = list(multimodal_context.get("attachments", []) or [])
        attachment_kinds = sorted({str(item.get("kind", "")) for item in attachment_items if item.get("kind")})
        message_type = "multimodal" if attachment_kinds else "text"
        remember_user_turn(
            db,
            session_id,
            user_memory_text or "",
            checkin,
            risk,
            metadata={"attachment_kinds": attachment_kinds},
            message_type=message_type,
            attachments=attachment_items,
        )
        memory_context = load_memory_context(db, session_id)
    agent_trace.append(
        {
            "agent": "MemoryAgent",
            "status": "completed",
            "summary": "已读取最近消息、滚动摘要、用户偏好和独立风险状态",
        }
    )

    media_analysis = multimodal_context.get("media_analysis", {})
    visual_affect = None
    if isinstance(media_analysis, dict):
        visual_affect = infer_visual_emotion(
            [str(item) for item in media_analysis.get("observable_cues", [])],
            media_analysis.get("visual_affect_candidates", []),
        )

    emotion = analyze_emotion(combined_text or message, checkin=checkin, face_emotion=visual_affect)
    emotion_evidence = split_emotion_evidence(evidence_objects, str(emotion.get("label", "neutral")))
    emotion.update(emotion_evidence)
    evidence_items = [
        {"source": source, "content": text[:160]}
        for source, text in risk_sources.items()
        if text
    ]
    if visual_affect:
        evidence_items.append(
            {
                "source": "visual_affect",
                "content": (
                    f"{visual_affect['label']} / {visual_affect['confidence']:.2f}；"
                    f"{visual_affect['evidence']}。该结果只代表可观察表情线索，不等同于真实心理状态。"
                ),
            }
        )
    emotion["evidence"] = evidence_items or [{"source": "system", "content": "未检测到明显文字、转写或视觉表情线索"}]
    agent_trace.append(
        {
            "agent": "EmotionAgent",
            "status": "completed",
            "summary": f"识别为 {emotion['label']}，强度 {emotion['intensity']}",
        }
    )

    if risk["level"] == "high":
        with SessionLocal() as db:
            remember_assistant_turn(
                db,
                session_id,
                CRISIS_REFERRAL_REPLY,
                {"risk_level": "high", "counselor_skipped": True},
            )
            metrics = record_request_metric(
                db,
                session_id=session_id,
                route="/api/chat/multimodal",
                total_duration_ms=int((time.perf_counter() - started) * 1000),
                stages={"risk_ms": int((time.perf_counter() - started) * 1000)},
                token_usage={"status": "not_applicable_high_risk"},
                provider="",
                model="",
                request_id="",
                success=True,
            )
        result = {
            "emotion": emotion,
            "risk": risk,
            "reply": CRISIS_REFERRAL_REPLY,
            "interventions": [
                {
                    "type": "crisis_referral",
                    "title": "立即联系可信任的人",
                    "description": "请优先联系身边可信任的人、学校辅导员、当地紧急服务或危机支持，并尽量不要独处。",
                }
            ],
            "agent_trace": [
                *agent_trace,
                {
                    "agent": "CoordinatorAgent",
                    "status": "completed",
                    "summary": "高风险命中，跳过普通 CounselorAgent",
                },
            ],
            "provider_metadata": {"llm_provider": None, "model": None, "request_id": None},
            "evidence": evidence_objects,
            "retrieval": {"retrieval_status": "skipped_high_risk", "retrieved_chunks": []},
            "request_metrics": metrics,
        }
        reviewed = review_response(
            {
                **result,
                "agent_trace": [f"{i['agent']}: {i['summary']}" for i in result["agent_trace"]],
            }
        )
        reviewed["agent_trace"] = [
            *result["agent_trace"],
            {"agent": "SafetyAgent", "status": "passed", "summary": "强制危机转介模板"},
        ]
        return reviewed

    agent_v2 = await _prepare_agent_v2(
        message=combined_text or message,
        emotion=emotion,
        risk=risk,
        checkin=checkin,
        multimodal_context=multimodal_context,
        session_id=session_id,
        recent_messages=memory_context["recent_messages"],
    )
    agent_trace.extend(agent_v2.get("agent_trace", []))

    interventions = recommend_interventions(
        emotion,
        checkin=checkin,
        risk=risk,
        memory=memory_context["snapshot"],
        knowledge_sources=agent_v2.get("knowledge_sources", []),
    )
    agent_trace.append(
        {
            "agent": "InterventionAgent",
            "status": "completed",
            "summary": f"推荐 {len(interventions)} 个自助调节动作",
        }
    )

    counselor_started = time.perf_counter()
    reply, provider_result, knowledge_sources, generation_metadata = await generate_counseling_reply(
        message=message or combined_text,
        emotion=emotion,
        risk=risk,
        interventions=interventions,
        checkin=checkin,
        multimodal_context=multimodal_context,
        session_id=session_id,
        memory=memory_context["snapshot"],
        recent_messages=memory_context["recent_messages"],
        evidence=evidence_objects,
        psychological_state=agent_v2.get("psychological_state") or None,
        strategy_plan=agent_v2.get("strategy_plan") or None,
        rag_route=agent_v2.get("rag_route") or None,
        knowledge_context=agent_v2.get("knowledge_context"),
    )
    counselor_ms = int((time.perf_counter() - counselor_started) * 1000)
    if knowledge_sources:
        interventions = recommend_interventions(
            emotion,
            checkin=checkin,
            risk=risk,
            memory=memory_context["snapshot"],
            knowledge_sources=knowledge_sources,
        )
    agent_trace.append(
        {
            "agent": "CounselorAgent",
            "status": "completed",
            "summary": "调用豆包生成回复",
        }
    )

    provider_metadata = {
        **provider_result.as_metadata(),
        "provider_calls": 1 + int(agent_v2.get("provider_calls", 0) or 0),
        **generation_metadata,
    }
    reviewed = await review_response_async(
        {
            "emotion": emotion,
            "risk": risk,
            "reply": reply,
            "interventions": interventions,
            "agent_trace": [f"{i['agent']}: {i['summary']}" for i in agent_trace],
            "provider_metadata": provider_metadata,
        }
    )
    agent_trace.extend(_safety_trace_to_structured(reviewed.get("agent_trace", [])))
    reviewed["agent_trace"] = agent_trace
    reviewed["provider_metadata"] = reviewed.get("provider_metadata", provider_metadata)
    reviewed["knowledge_sources"] = knowledge_sources
    reviewed["evidence"] = evidence_objects
    reviewed["retrieval"] = generation_metadata.get("retrieval", {})
    reviewed["psychological_state"] = agent_v2.get("psychological_state", {})
    reviewed["strategy_plan"] = agent_v2.get("strategy_plan", {})
    reviewed["rag_route"] = agent_v2.get("rag_route", {})
    final_risk = reviewed.get("risk", risk)
    with SessionLocal() as db:
        remember_assistant_turn(
            db,
            session_id,
            reviewed["reply"],
            {
                "risk_level": final_risk.get("level"),
                "emotion": emotion.get("label"),
                "psychological_state": agent_v2.get("psychological_state", {}),
                "strategy_plan": agent_v2.get("strategy_plan", {}),
                "rag_route": agent_v2.get("rag_route", {}),
                "knowledge_source_ids": [item.get("source_id") for item in knowledge_sources],
            },
        )
        token_usage = provider_result.usage or generation_metadata.get("context_token_usage") or {"status": "unknown"}
        token_usage = {**token_usage, "provider_calls": 1 + int(agent_v2.get("provider_calls", 0) or 0)}
        reviewed["request_metrics"] = record_request_metric(
            db,
            session_id=session_id,
            route="/api/chat/multimodal",
            total_duration_ms=int((time.perf_counter() - started) * 1000),
            stages={
                "total_ms": int((time.perf_counter() - started) * 1000),
                **agent_v2.get("stages", {}),
                "rag_ms": int(generation_metadata.get("retrieval", {}).get("duration_ms", 0) or 0),
                "counselor_ms": counselor_ms,
            },
            token_usage=token_usage,
            provider=provider_result.provider,
            model=provider_result.model,
            request_id=provider_result.request_id or "",
            success=True,
        )
    return reviewed
