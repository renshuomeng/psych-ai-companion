from __future__ import annotations

import time
from typing import Any

from agents.coordinator_agent import _prepare_agent_v2
from agents.counselor_agent import generate_counseling_reply
from agents.emotion_agent import analyze_emotion
from agents.intervention_agent import recommend_interventions
from agents.risk_agent import assess_risk
from agents.safety_agent import CRISIS_REFERRAL_REPLY, review_response
from ..schemas import AblationConfig, CandidateResult, EvaluationCase
from ..settings_override import temporary_ablation


class FullAgentEvaluationAdapter:
    def __init__(self, system_id: str, ablation: AblationConfig) -> None:
        self.system_id = system_id
        self.ablation = ablation

    async def generate(self, case: EvaluationCase, *, dry_run: bool = False, run_id: str = "") -> CandidateResult:
        started = time.perf_counter()
        session_id = f"eval_{run_id or 'adhoc'}_{case.case_id}"
        recent_messages: list[dict[str, Any]] = []
        final_result: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        with temporary_ablation(self.ablation):
            for turn_index, message in enumerate(case.turns):
                risk = assess_risk(message) if self.ablation.risk else {
                    "level": "low",
                    "reason": "RiskAgent disabled by evaluation ablation.",
                    "action": "continue_support",
                }
                emotion = analyze_emotion(message)
                trace: list[dict[str, Any] | str] = [
                    {"agent": "RiskAgent", "status": "completed" if self.ablation.risk else "disabled", "summary": risk.get("level", "low")},
                    {"agent": "EmotionAgent", "status": "completed", "summary": f"{emotion.get('label')} / {emotion.get('intensity')}"},
                ]

                if risk.get("level") == "high" and self.ablation.risk:
                    final_result = {
                        "emotion": emotion,
                        "risk": risk,
                        "reply": CRISIS_REFERRAL_REPLY,
                        "interventions": [
                            {
                                "type": "crisis_referral",
                                "title": "立即联系可信任的人",
                                "description": "优先联系可信任的人、学校辅导员、急救电话或危机支持。",
                            }
                        ],
                        "agent_trace": [*trace, {"agent": "CoordinatorAgent", "status": "completed", "summary": "高风险命中，跳过普通生成"}],
                        "knowledge_sources": [],
                        "psychological_state": {},
                        "strategy_plan": {},
                        "rag_route": {},
                        "provider_metadata": {"provider_calls": 0},
                    }
                    if self.ablation.safety:
                        reviewed = review_response({**final_result, "agent_trace": [str(item) for item in final_result["agent_trace"]]})
                        final_result["reply"] = reviewed["reply"]
                        final_result["interventions"] = reviewed["interventions"]
                        final_result["agent_trace"] = [
                            *final_result["agent_trace"],
                            {"agent": "SafetyAgent", "status": "passed", "summary": "强制危机转介模板"},
                        ]
                    break

                agent_v2 = await _prepare_agent_v2(
                    message=message,
                    emotion=emotion,
                    risk=risk,
                    session_id=session_id,
                    recent_messages=recent_messages,
                )
                trace.extend(agent_v2.get("agent_trace", []))
                if not self.ablation.rag:
                    trace.append({"agent": "RetrievalAgent", "status": "disabled", "summary": "RAG disabled by evaluation ablation"})

                interventions = recommend_interventions(
                    emotion,
                    risk=risk,
                    knowledge_sources=agent_v2.get("knowledge_sources", []),
                )
                trace.append({"agent": "InterventionAgent", "status": "completed", "summary": f"{len(interventions)} interventions"})

                if dry_run:
                    reply = (
                        "我能感觉到这件事让你有些吃力。我们先不急着把所有问题一次解决，"
                        "可以先选一个最小步骤：写下现在最困扰你的一个点，再决定下一步。"
                    )
                    provider_metadata = {"provider": "dry_run_mock", "provider_calls": 0}
                    knowledge_sources = agent_v2.get("knowledge_sources", [])
                    generation_metadata = {"retrieval": agent_v2.get("knowledge_context", {})}
                else:
                    try:
                        reply, provider_result, knowledge_sources, generation_metadata = await generate_counseling_reply(
                            message=message,
                            emotion=emotion,
                            risk=risk,
                            interventions=interventions,
                            session_id=session_id,
                            recent_messages=recent_messages,
                            psychological_state=agent_v2.get("psychological_state") or None,
                            strategy_plan=agent_v2.get("strategy_plan") or None,
                            rag_route=agent_v2.get("rag_route") or None,
                            knowledge_context=agent_v2.get("knowledge_context"),
                        )
                        provider_metadata = {
                            **provider_result.as_metadata(),
                            "provider_calls": 1 + int(agent_v2.get("provider_calls", 0) or 0),
                            **generation_metadata,
                        }
                    except Exception as exc:
                        errors.append({"stage": "CounselorAgent", "type": type(exc).__name__, "message": str(exc)[:300]})
                        reply = "本轮模型生成失败，评价中心已记录错误；请检查后端模型服务配置后重试。"
                        provider_metadata = {"provider": "error", "provider_calls": 0}
                        knowledge_sources = agent_v2.get("knowledge_sources", [])
                        generation_metadata = {"retrieval": agent_v2.get("knowledge_context", {})}

                result = {
                    "emotion": emotion,
                    "risk": risk,
                    "reply": reply,
                    "interventions": interventions,
                    "agent_trace": [str(item) for item in trace],
                    "provider_metadata": provider_metadata,
                    "knowledge_sources": knowledge_sources,
                    "psychological_state": agent_v2.get("psychological_state", {}),
                    "strategy_plan": agent_v2.get("strategy_plan", {}),
                    "rag_route": agent_v2.get("rag_route", {}),
                    "retrieval": generation_metadata.get("retrieval", {}),
                }
                if self.ablation.safety:
                    result = review_response(result)
                    trace.append({"agent": "SafetyAgent", "status": "passed", "summary": "完成安全审查"})
                else:
                    trace.append({"agent": "SafetyAgent", "status": "disabled", "summary": "Safety disabled by evaluation ablation"})
                result["agent_trace"] = trace
                final_result = result
                recent_messages.extend(
                    [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": result["reply"]},
                    ]
                )

        return CandidateResult(
            system_id=self.system_id,
            response=str(final_result.get("reply", "")),
            latency_ms=int((time.perf_counter() - started) * 1000),
            risk=final_result.get("risk", {}),
            emotion=final_result.get("emotion", {}),
            psychological_state=final_result.get("psychological_state", {}),
            strategy_plan=final_result.get("strategy_plan", {}),
            rag_route=final_result.get("rag_route", {}),
            knowledge_sources=final_result.get("knowledge_sources", []),
            interventions=final_result.get("interventions", []),
            provider_metadata=final_result.get("provider_metadata", {}),
            trace=final_result.get("agent_trace", []),
            errors=errors,
        )
