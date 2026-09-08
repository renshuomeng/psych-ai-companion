from pathlib import Path
from typing import Any

from evaluation.metrics.classification_metrics import classification_report
from evaluation.metrics.safety_metrics import safety_report
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from agents.risk_agent import assess_risk


def evaluate_risk(output_dir: Path | None = None) -> dict[str, Any]:
    cases = read_jsonl(DATASET_DIR / "risk_cases.jsonl")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        result = assess_risk(case["input"].get("text", ""))
        dims = result.get("dimensions", {})
        row = {
            "case_id": case["case_id"],
            "expected": case["expected"]["level"],
            "predicted": result["level"],
            "action": result["action"],
            "negated_expected": bool(case["expected"].get("negated")),
            "negated_predicted": bool(dims.get("negated")),
            "third_party_expected": bool(case["expected"].get("third_party_report")),
            "third_party_predicted": bool(dims.get("third_party_report")),
        }
        rows.append(row)
        if row["expected"] != row["predicted"]:
            failures.append({**row, "input": case["input"], "risk": result})
    report = {
        "metrics": {**classification_report(rows), **safety_report(rows)},
        "cases": rows,
        "failures": failures,
    }
    if output_dir:
        write_json(output_dir / "risk_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_risk(args.output_dir)["metrics"])
