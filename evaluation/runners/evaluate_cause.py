from pathlib import Path
from typing import Any

from evaluation.metrics.classification_metrics import classification_report
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from services.psychological_state_service import classify_cause


def evaluate_cause(output_dir: Path | None = None) -> dict[str, Any]:
    cases = read_jsonl(DATASET_DIR / "cause_cases.jsonl")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        result = classify_cause(case["input"].get("text", ""))
        row = {
            "case_id": case["case_id"],
            "expected": case["expected"]["cause"],
            "predicted": result["label"],
            "confidence": result["confidence"],
            "evidence": result["evidence"],
        }
        rows.append(row)
        if row["expected"] != row["predicted"]:
            failures.append({**row, "input": case["input"]})
    report = {"metrics": classification_report(rows), "cases": rows, "failures": failures}
    if output_dir:
        write_json(output_dir / "cause_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_cause(args.output_dir)["metrics"])
