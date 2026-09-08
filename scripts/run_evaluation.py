import argparse
import json

import _bootstrap  # noqa: F401
from evaluation.runners.run_full_evaluation import run_full_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full offline evaluation.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_full_evaluation()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['status']}")
        print(f"output_dir: {result['output_dir']}")
        print(f"failure_count: {result['summary']['failure_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
