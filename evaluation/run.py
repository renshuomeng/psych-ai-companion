from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for path in [str(BACKEND), str(ROOT)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.evaluation.runner import compare_runs, run_evaluation_sync
from backend.evaluation.schemas import AblationConfig, RunConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CARE-Psy Competition Evaluation Center V1")
    parser.add_argument("--system", default="full_agent")
    parser.add_argument("--framework", action="append", dest="frameworks", help="Repeatable. all = every framework.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", dest="resume_run_id")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-risk", action="store_true")
    parser.add_argument("--no-psychological-state", action="store_true")
    parser.add_argument("--no-strategy", action="store_true")
    parser.add_argument("--no-rag", action="store_true")
    parser.add_argument("--no-safety", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--baseline-run")
    parser.add_argument("--candidate-run")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.compare:
        if not args.baseline_run or not args.candidate_run:
            raise SystemExit("--compare requires --baseline-run and --candidate-run")
        print(json.dumps(compare_runs(args.baseline_run, args.candidate_run), ensure_ascii=False, indent=2))
        return

    frameworks = args.frameworks or ["care_bench", "esc_eval", "cpsycoun", "counselbench"]
    if "all" in frameworks:
        frameworks = ["care_bench", "esc_eval", "cpsycoun", "counselbench"]
    ablation = AblationConfig.for_system(args.system)
    if args.no_risk or args.no_psychological_state or args.no_strategy or args.no_rag or args.no_safety:
        ablation = AblationConfig(
            risk=not args.no_risk,
            psychological_state=not args.no_psychological_state,
            strategy=not args.no_strategy,
            rag=not args.no_rag,
            safety=not args.no_safety,
        )

    config = RunConfig(
        system_id=args.system,
        frameworks=frameworks,
        limit=args.limit,
        dry_run=args.dry_run,
        resume_run_id=args.resume_run_id,
        ablation=ablation,
        use_cache=not args.no_cache,
    )
    print(json.dumps(run_evaluation_sync(config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

