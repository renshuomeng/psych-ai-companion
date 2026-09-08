from pathlib import Path
from typing import Any

from evaluation.metrics.classification_metrics import classification_report
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from agents.emotion_agent import analyze_emotion


def evaluate_emotion(output_dir: Path | None = None) -> dict[str, Any]:
    cases = read_jsonl(DATASET_DIR / "emotion_cases.jsonl")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    interval_hits = 0
    for case in cases:
        result = analyze_emotion(
            case["input"].get("text", ""),
            checkin=case["input"].get("checkin"),
        )
        expected = case["expected"]["primary_label"]
        predicted = result["label"]
        interval = case["expected"].get("intensity_range", [0, 1])
        in_range = interval[0] <= result["intensity"] <= interval[1]
        interval_hits += int(in_range)
        row = {
            "case_id": case["case_id"],
            "expected": expected,
            "predicted": predicted,
            "intensity": result["intensity"],
            "intensity_in_range": in_range,
        }
        rows.append(row)
        if expected != predicted or not in_range:
            failures.append({**row, "input": case["input"]})
    metrics = classification_report(rows)
    metrics["intensity_interval_accuracy"] = interval_hits / len(cases) if cases else 0.0
    report = {"metrics": metrics, "cases": rows, "failures": failures}
    if output_dir:
        write_json(output_dir / "emotion_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_emotion(args.output_dir)["metrics"])
