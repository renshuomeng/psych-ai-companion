from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in [str(BACKEND), str(ROOT)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from config import get_settings
from schemas.errors import AppError
from services.ark_client import chat


AGENTS = {
    "default": "Default Doubao",
    "counselor": "CounselorAgent",
    "analyzer": "PsychologicalStateAnalyzer",
    "planner": "StrategyPlanner",
    "safety": "SafetyAgent",
}


def static_status() -> dict[str, Any]:
    settings = get_settings()
    models = {}
    for agent_key, display_name in AGENTS.items():
        model_id = settings.doubao_model_for_agent(agent_key)
        models[agent_key] = {
            "agent": display_name,
            "configured": bool(model_id),
            "model_id": model_id,
            "temperature": settings.doubao_temperature_for_agent(agent_key),
        }

    judge_remote = settings.eval_judge_provider.strip().lower() not in {"heuristic_local", "local", ""}
    judge_model_configured = bool(settings.eval_judge_model_id.strip()) if judge_remote else True
    return {
        "provider": settings.llm_provider,
        "ark_base_url": settings.ark_base_url,
        "ark_api_key_configured": settings.ark_configured,
        "timeout_seconds": settings.effective_doubao_timeout_seconds,
        "retry_attempts": settings.effective_doubao_retry_attempts,
        "max_tokens": settings.doubao_max_tokens,
        "models": models,
        "judge": {
            "provider": settings.eval_judge_provider,
            "model_id": settings.eval_judge_model_id,
            "remote_judge": judge_remote,
            "configured": judge_model_configured,
            "self_judge_guardrail": "candidate_and_judge_are_configured_independently",
        },
        "configuration_valid": settings.ark_configured and all(item["configured"] for item in models.values()),
    }


async def live_status() -> dict[str, Any]:
    try:
        result = await chat(
            [{"role": "user", "content": "请只回复：OK"}],
            agent_name="default",
            temperature=0.0,
            max_tokens=8,
            stage="doubao_health_check",
        )
    except AppError as exc:
        return {
            "live_status": "failed",
            "error": {
                "code": exc.detail.code,
                "message": exc.detail.message,
                "stage": exc.detail.stage,
                "retryable": exc.detail.retryable,
                "request_id": exc.detail.request_id,
            },
        }
    except Exception as exc:
        return {"live_status": "failed", "error": {"type": type(exc).__name__, "message": str(exc)[:300]}}

    return {
        "live_status": "passed",
        "response_nonempty": bool(result.text.strip()),
        "model": result.model,
        "request_id": result.request_id,
        "latency_ms": result.latency_ms,
        "finish_reason": result.finish_reason,
        "usage": result.usage,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CARE-Psy Volcengine Ark / Doubao LLM configuration.")
    parser.add_argument("--live", action="store_true", help="Send one tiny health-check request to Ark.")
    parser.add_argument("--json", action="store_true", help="Print JSON. This is the default format.")
    args = parser.parse_args()

    status = static_status()
    if args.live:
        status["live_check"] = asyncio.run(live_status())
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
