from __future__ import annotations

from typing import Any


FRAMEWORK_REGISTRY: dict[str, dict[str, Any]] = {
    "care_bench": {
        "name": "CARE-Bench",
        "official_status": "Partial",
        "local_status": "Compatible",
        "note": "V1 keeps official dimension names and uses a local smoke heuristic. Official evaluator is not vendored.",
        "metrics": [
            {"name": "WAI Goal", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "WAI Task", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "WAI Bond", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "BLRI Cognitive Empathy", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "BLRI Affective Empathy", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "BLRI Differentiated Empathy", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "BLRI Inner Pattern", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "CCS-R Probing", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "CCS-R Therapeutic Environment", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "CCS-R Reflecting", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "CCS-R Change Facilitation", "direction": "higher_is_better", "scale": [1, 5]},
        ],
    },
    "esc_eval": {
        "name": "ESC-Eval",
        "official_status": "Unavailable",
        "local_status": "Compatible",
        "note": "Official metrics are preserved; local V1 uses a smoke heuristic until official resources are integrated.",
        "metrics": [
            {"name": "Fluency", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Expression", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Empathy", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Information", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Humanoid", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Skillful", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Overall", "direction": "higher_is_better", "scale": [1, 5]},
        ],
    },
    "cpsycoun": {
        "name": "CPsyCounE",
        "official_status": "Partial",
        "local_status": "Compatible",
        "note": "V1 keeps the CPsyCounE evaluation axes and reports heuristic compatibility scores only.",
        "metrics": [
            {"name": "Comprehensiveness", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Professionalism", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Authenticity", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Safety", "direction": "higher_is_better", "scale": [1, 5]},
        ],
    },
    "counselbench": {
        "name": "CounselBench",
        "official_status": "Unavailable",
        "local_status": "Compatible",
        "note": "V1 records the official-style dimensions; Medical Advice and Toxicity are lower-is-better.",
        "metrics": [
            {"name": "Overall Quality", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Empathy", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Specificity", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Medical Advice", "direction": "lower_is_better", "scale": [0, 5]},
            {"name": "Factual Consistency", "direction": "higher_is_better", "scale": [1, 5]},
            {"name": "Toxicity", "direction": "lower_is_better", "scale": [0, 5]},
        ],
    },
}


SYSTEM_REGISTRY: dict[str, dict[str, Any]] = {
    "direct_doubao": {
        "name": "Direct Doubao",
        "description": "Direct base-model call without CARE-Psy RiskAgent, PsychologicalStateAnalyzer, StrategyPlanner, RAG, or SafetyAgent.",
    },
    "full_agent": {
        "name": "Current Full Agent",
        "description": "RiskAgent + EmotionAgent + PsychologicalStateAnalyzer + StrategyPlanner + RAG Router/Retrieval + CounselorAgent + SafetyAgent.",
    },
    "agent_without_rag": {
        "name": "Agent without RAG",
        "description": "Full agent with RAG router/retrieval disabled.",
    },
    "agent_without_strategy": {
        "name": "Agent without StrategyPlanner",
        "description": "Full agent with StrategyPlanner disabled through existing feature flag.",
    },
    "agent_without_psychological_state": {
        "name": "Agent without PsychologicalStateAnalyzer",
        "description": "Full agent with PsychologicalStateAnalyzer disabled through existing feature flag.",
    },
    "custom_agent": {
        "name": "Custom Ablation",
        "description": "User-selected ablation switches for risk, psychological state, strategy, RAG, and safety.",
    },
}


def list_frameworks() -> dict[str, Any]:
    return FRAMEWORK_REGISTRY


def list_systems() -> dict[str, Any]:
    return SYSTEM_REGISTRY

