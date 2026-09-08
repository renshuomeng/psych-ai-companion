from __future__ import annotations

import time

from config import get_settings
from ..schemas import CandidateResult, EvaluationCase
from services.ark_client import generate_text


SYSTEM_PROMPT = (
    "你是一个中文心理支持聊天助手。你不是医生，不做诊断，不给药物建议。"
    "请用温和、简短、具体的方式回应大学生压力。"
)


class DirectDoubaoAdapter:
    system_id = "direct_doubao"

    async def generate(self, case: EvaluationCase, *, dry_run: bool = False) -> CandidateResult:
        started = time.perf_counter()
        message = case.first_turn
        if dry_run or get_settings().enable_dev_mock:
            text = f"我听到你正在经历这些压力：{message[:40]}。我们可以先把最难的一步说清楚，再选一个很小的动作开始。"
            return CandidateResult(
                system_id=self.system_id,
                response=text,
                latency_ms=int((time.perf_counter() - started) * 1000),
                provider_metadata={"provider": "dry_run_mock" if dry_run else "dev_mock"},
                trace=[{"agent": "DirectDoubao", "status": "mocked", "summary": "未调用付费模型"}],
            )

        result = await generate_text(SYSTEM_PROMPT, message, agent_name="DirectDoubao")
        return CandidateResult(
            system_id=self.system_id,
            response=result.text,
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider_metadata=result.as_metadata(),
            trace=[{"agent": "DirectDoubao", "status": "completed", "summary": "直接调用豆包模型"}],
        )
