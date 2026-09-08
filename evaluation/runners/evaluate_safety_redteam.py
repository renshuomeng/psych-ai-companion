from pathlib import Path
from typing import Any

from evaluation.metrics.classification_metrics import classification_report
from evaluation.metrics.safety_metrics import safety_report
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from agents.risk_agent import assess_risk


def evaluate_safety_redteam(output_dir: Path | None = None) -> dict[str, Any]:
    cases = read_jsonl(DATASET_DIR / "safety_redteam.jsonl")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    generation_checks_skipped = []
    for case in cases:
        expected = case.get("expected", {})
        risk = assess_risk(case["input"].get("text", ""))
        expected_level = expected.get("level", "low")
        row = {
            "case_id": case["case_id"],
            "expected": expected_level,
            "predicted": risk["level"],
            "action": risk["action"],
            "negated_expected": bool(expected.get("negated")),
            "negated_predicted": bool(risk.get("dimensions", {}).get("negated")),
            "third_party_expected": bool(expected.get("third_party_report")),
            "third_party_predicted": bool(risk.get("dimensions", {}).get("third_party_report")),
        }
        rows.append(row)
        if row["expected"] != row["predicted"]:
            failures.append({**row, "input": case["input"], "risk": risk})
        if any(key in expected for key in ("diagnosis_violation", "medication_violation", "prompt_injection_success")):
            generation_checks_skipped.append(
                {
                    "case_id": case["case_id"],
                    "reason": "当前 runner 只评测规则风险闸门；生成式安全越狱需要调用完整 Counselor + SafetyAgent 链路。",
                }
            )
    report = {
        "metrics": {**classification_report(rows), **safety_report(rows)},
        "cases": rows,
        "failures": failures,
        "generation_checks_skipped": generation_checks_skipped,
    }
    if output_dir:
        write_json(output_dir / "safety_redteam_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_safety_redteam(args.output_dir)["metrics"])
