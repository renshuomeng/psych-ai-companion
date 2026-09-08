from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for item in (str(ROOT), str(BACKEND)):
    if item not in sys.path:
        sys.path.insert(0, item)

from backend.evaluation.runner import compare_runs, run_evaluation_sync
from backend.evaluation.schemas import AblationConfig, RunConfig


OUT = ROOT / "evaluation" / "results" / "ablation"
DEFAULT_FRAMEWORKS = ["care_bench", "esc_eval", "cpsycoun", "counselbench"]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _flatten_comparison(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for framework_id, framework in comparison.get("metric_delta", {}).items():
        for metric_name, metric in framework.get("metrics", {}).items():
            rows.append(
                {
                    "framework_id": framework_id,
                    "metric_name": metric_name,
                    "baseline_mean": metric.get("baseline_mean"),
                    "candidate_mean": metric.get("candidate_mean"),
                    "delta": metric.get("delta"),
                    "direction": metric.get("direction"),
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["framework_id", "metric_name", "baseline_mean", "candidate_mean", "delta", "direction"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_rag_ablation(*, limit: int, frameworks: list[str], dry_run: bool, use_cache: bool) -> dict[str, Any]:
    baseline = run_evaluation_sync(
        RunConfig(
            system_id="agent_without_rag",
            frameworks=frameworks,
            limit=limit,
            dry_run=dry_run,
            ablation=AblationConfig.for_system("agent_without_rag"),
            use_cache=use_cache,
        )
    )
    candidate = run_evaluation_sync(
        RunConfig(
            system_id="full_agent",
            frameworks=frameworks,
            limit=limit,
            dry_run=dry_run,
            ablation=AblationConfig.for_system("full_agent"),
            use_cache=use_cache,
        )
    )
    comparison = compare_runs(baseline["run_id"], candidate["run_id"])
    report = {
        "status": "completed",
        "note": (
            "Smoke comparison only. The Evaluation Center uses local compatibility scoring; "
            "it does not claim official CARE-Bench/ESC-Eval/CPsyCounE/CounselBench results."
        ),
        "baseline_system": "agent_without_rag",
        "candidate_system": "full_agent",
        "limit": limit,
        "frameworks": frameworks,
        "dry_run": dry_run,
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "baseline_output_dir": baseline["output_dir"],
        "candidate_output_dir": candidate["output_dir"],
        "comparison": comparison,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUT / "rag_v2_no_rag_vs_full_agent.json", report)
    _write_csv(OUT / "rag_v2_no_rag_vs_full_agent.csv", _flatten_comparison(comparison))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CARE-Psy RAG V2 No-RAG vs Full-Agent smoke comparison.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--framework", action="append", dest="frameworks", help="Repeatable. Use all for every framework.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Use dry-run candidate replies by default.")
    parser.add_argument("--real-generation", action="store_true", help="Allow real configured model generation.")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    frameworks = args.frameworks or DEFAULT_FRAMEWORKS
    if "all" in frameworks:
        frameworks = DEFAULT_FRAMEWORKS
    report = run_rag_ablation(
        limit=args.limit,
        frameworks=frameworks,
        dry_run=not args.real_generation,
        use_cache=not args.no_cache,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"baseline_run_id: {report['baseline_run_id']}")
        print(f"candidate_run_id: {report['candidate_run_id']}")
        print(f"comparison_json: {(OUT / 'rag_v2_no_rag_vs_full_agent.json').as_posix()}")
        print(f"comparison_csv: {(OUT / 'rag_v2_no_rag_vs_full_agent.csv').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
