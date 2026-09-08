import argparse
import csv
import json
from pathlib import Path

import _bootstrap  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "competition_results"


def _latest_summary() -> dict:
    results = ROOT / "evaluation" / "results"
    summaries = sorted(results.glob("*/summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not summaries:
        return {"status": "no_evaluation_run"}
    return json.loads(summaries[0].read_text(encoding="utf-8"))


def _write_csv(path: Path, data: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key, value in data.items():
            writer.writerow([key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value])


def main() -> int:
    parser = argparse.ArgumentParser(description="Export competition report materials.")
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    summary = _latest_summary()
    overview = {
        "system": "AI 心理陪伴 Web 系统",
        "modules": ["MultimodalAgent", "RiskAgent", "MemoryAgent", "RetrievalAgent", "EmotionAgent", "InterventionAgent", "CounselorAgent", "SafetyAgent"],
        "rag": "local deterministic embedding + vector search + BM25/SQLite FTS keyword search + emotion-aware metadata rerank + low relevance rejection",
        "memory": "recent messages + rolling structured summary + confirmed profile + independent risk state",
        "safety": "rule-first high risk detection; high risk does not depend on provider availability",
    }
    (OUT / "system_overview.json").write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(OUT / "evaluation_summary.csv", summary)
    _write_csv(OUT / "safety_summary.csv", summary.get("risk", {}))
    _write_csv(OUT / "rag_summary.csv", summary.get("rag", {}))
    _write_csv(OUT / "latency_summary.csv", summary.get("latency", {}))
    _write_csv(OUT / "cost_summary.csv", {"cost_status": summary.get("latency", {}).get("cost_status", "unknown")})
    _write_csv(OUT / "ablation_summary.csv", {"status": "skipped_by_user_request"})
    (OUT / "report_materials.md").write_text(
        "# 竞赛报告材料\n\n"
        "## 系统模块\n"
        "- 多模态输入、统一证据对象、风险预检查、RAG、分层记忆、干预闭环、安全审查。\n\n"
        "## 技术路线\n"
        "- 先建立固定评测集，再构建知识库检索、记忆压缩和安全闭环。\n\n"
        "## 系统限制\n"
        "- 当前内置知识资料为 source_unverified，正式展示前应替换为已审核资料。\n"
        "- 本系统不构成医学诊断、药物建议或治疗承诺。\n",
        encoding="utf-8",
    )
    print(f"exported: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
