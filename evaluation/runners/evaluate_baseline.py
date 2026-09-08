from pathlib import Path
from typing import Any

from evaluation.runners.common import write_json


def evaluate_baseline(
    output_dir: Path | None = None,
    current_agent_summary: dict[str, Any] | None = None,
    run_real_api: bool = False,
) -> dict[str, Any]:
    report = {
        "comparison": {
            "doubao_direct_response": {
                "status": "skipped" if not run_real_api else "not_implemented",
                "reason": (
                    "默认不调用真实大模型 API，避免在完整评测中产生费用或速率限制；"
                    "后续可用统一提示词单独补 Doubao direct baseline。"
                    if not run_real_api
                    else "本轮按 Phase 0-3 优先完成离线可复现基线，尚未实现真实 API 批量直连评测。"
                ),
            },
            "current_agent_system": {
                "status": "completed" if current_agent_summary else "available_via_run_full_evaluation",
                "summary": current_agent_summary or {},
            },
        },
        "method_table": [
            {"method": "Doubao", "RAG": False, "Memory": False, "Strategy": False, "EmotionRAG": False, "Critic": False},
            {"method": "Prompt", "RAG": False, "Memory": False, "Strategy": True, "EmotionRAG": False, "Critic": False},
            {"method": "RAG", "RAG": True, "Memory": False, "Strategy": False, "EmotionRAG": False, "Critic": False},
            {"method": "Memory", "RAG": False, "Memory": True, "Strategy": False, "EmotionRAG": False, "Critic": False},
            {"method": "EmotionRAG", "RAG": True, "Memory": False, "Strategy": True, "EmotionRAG": True, "Critic": False},
            {"method": "Full", "RAG": True, "Memory": True, "Strategy": True, "EmotionRAG": True, "Critic": True},
        ],
        "note": "消融实验本轮按用户要求不运行；该表只保留方法定义，不报告未运行数值。",
    }
    if output_dir:
        write_json(output_dir / "baseline_comparison.json", report)
    return report


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--real-api", action="store_true")
    args = parser.parse_args()
    print(json.dumps(evaluate_baseline(args.output_dir, run_real_api=args.real_api), ensure_ascii=False, indent=2))
