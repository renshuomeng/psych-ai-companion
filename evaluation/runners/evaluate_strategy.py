from pathlib import Path
from typing import Any

from evaluation.metrics.classification_metrics import classification_report
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from services.psychological_state_service import classify_strategy


def evaluate_strategy(output_dir: Path | None = None) -> dict[str, Any]:
    cases = read_jsonl(DATASET_DIR / "strategy_cases.jsonl")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        input_data = case.get("input", {})
        result = classify_strategy(
            input_data.get("text", ""),
            emotion=input_data.get("emotion"),
            risk=input_data.get("risk"),
            interventions=input_data.get("interventions"),
        )
        row = {
            "case_id": case["case_id"],
            "expected": case["expected"]["strategy"],
            "predicted": result["label"],
            "confidence": result["confidence"],
            "evidence": result["evidence"],
            "method": result["method"],
        }
        rows.append(row)
        if row["expected"] != row["predicted"]:
            failures.append({**row, "input": input_data})
    report = {"metrics": classification_report(rows), "cases": rows, "failures": failures}
    if output_dir:
        write_json(output_dir / "strategy_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_strategy(args.output_dir)["metrics"])
