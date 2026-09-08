import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.runners.common import RESULTS_DIR, write_json, write_jsonl
from evaluation.runners.evaluate_baseline import evaluate_baseline
from evaluation.runners.evaluate_cause import evaluate_cause
from evaluation.runners.evaluate_emotion import evaluate_emotion
from evaluation.runners.evaluate_latency import evaluate_latency
from evaluation.runners.evaluate_memory import evaluate_memory
from evaluation.runners.evaluate_rag import evaluate_rag
from evaluation.runners.evaluate_risk import evaluate_risk
from evaluation.runners.evaluate_safety_redteam import evaluate_safety_redteam
from evaluation.runners.evaluate_strategy import evaluate_strategy

from database.db import SessionLocal, init_db
from database.models import EvaluationRun


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "not_a_git_repository"


def _html_report(summary: dict[str, Any]) -> str:
    body = json.dumps(summary, ensure_ascii=False, indent=2)
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>AI 心理陪伴系统评测报告</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:32px;line-height:1.6;color:#172033}}pre{{background:#f4f7fb;padding:16px;border-radius:8px;white-space:pre-wrap}}.warn{{color:#b45309}}</style></head>
<body>
<h1>AI 心理陪伴系统评测报告</h1>
<p class="warn">本报告只展示实际运行得到的数据，不伪造未运行实验。</p>
<pre>{body}</pre>
</body></html>"""


def run_full_evaluation() -> dict[str, Any]:
    init_db()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RESULTS_DIR / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    emotion = evaluate_emotion(output_dir)
    cause = evaluate_cause(output_dir)
    strategy = evaluate_strategy(output_dir)
    risk = evaluate_risk(output_dir)
    safety_redteam = evaluate_safety_redteam(output_dir)
    rag = evaluate_rag(output_dir)
    memory = evaluate_memory(output_dir)
    latency = evaluate_latency(output_dir)
    failures = []
    for name, report in [
        ("emotion", emotion),
        ("cause", cause),
        ("strategy", strategy),
        ("risk", risk),
        ("safety_redteam", safety_redteam),
    ]:
        for item in report.get("failures", []):
            failures.append({"suite": name, **item})
    write_jsonl(output_dir / "failures.jsonl", failures)

    summary = {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "git_commit": _git_commit(),
        "emotion": emotion["metrics"],
        "cause": cause["metrics"],
        "strategy": strategy["metrics"],
        "risk": risk["metrics"],
        "safety_redteam": safety_redteam["metrics"],
        "rag": rag["modes"],
        "memory": memory["metrics"],
        "latency": latency["metrics"],
        "failure_count": len(failures),
    }
    baseline = evaluate_baseline(
        output_dir,
        current_agent_summary={
            "emotion_macro_f1": emotion["metrics"].get("macro_f1"),
            "cause_accuracy": cause["metrics"].get("accuracy"),
            "strategy_accuracy": strategy["metrics"].get("accuracy"),
            "risk_recall": risk["metrics"].get("high_risk_recall"),
            "rag_modes": rag["modes"],
            "memory": memory["metrics"],
            "latency": latency["metrics"],
        },
    )
    summary["baseline"] = baseline["comparison"]
    summary["ablation"] = {"status": "skipped_by_user_request"}
    write_json(output_dir / "summary.json", summary)
    (output_dir / "evaluation_report.html").write_text(_html_report(summary), encoding="utf-8")
    with SessionLocal() as db:
        db.add(
            EvaluationRun(
                run_id=uuid.uuid4().hex,
                status="completed",
                config_json=json.dumps({"runner": "run_full_evaluation"}, ensure_ascii=False),
                summary_json=json.dumps(summary, ensure_ascii=False),
                output_dir=str(output_dir),
            )
        )
        db.commit()
    return {"status": "completed", "output_dir": str(output_dir), "summary": summary}


if __name__ == "__main__":
    print(json.dumps(run_full_evaluation(), ensure_ascii=False, indent=2))
