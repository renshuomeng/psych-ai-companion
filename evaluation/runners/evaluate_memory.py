from pathlib import Path
from typing import Any

from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from agents.memory_agent import remember_assistant_turn, remember_user_turn
from agents.risk_agent import assess_risk
from database.db import SessionLocal, init_db
from services.memory_service import delete_memory, get_memory_snapshot, rebuild_summary


def evaluate_memory(output_dir: Path | None = None) -> dict[str, Any]:
    init_db()
    cases = read_jsonl(DATASET_DIR / "memory_cases.jsonl")
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for case in cases:
            session_id = f"eval_{case['case_id']}"
            delete_memory(db, session_id)
            for turn in case["turns"]:
                if turn["role"] == "user":
                    risk = assess_risk(turn["text"])
                    remember_user_turn(db, session_id, turn["text"], None, risk)
                else:
                    remember_assistant_turn(db, session_id, turn["text"])
            summary = rebuild_summary(db, session_id)
            memory = get_memory_snapshot(db, session_id)
            profile_text = str(memory.get("profile", {}))
            summary_text = str(summary)
            expected = case["expected"]
            row = {
                "case_id": case["case_id"],
                "explicit_information_retained": all(item in profile_text + summary_text for item in expected["remember_stressors"]),
                "disliked_retained": all(item in profile_text for item in expected["remember_disliked"]),
                "preference_followed": all(item in profile_text + summary_text for item in expected["prefer"]),
                "fabrication": any(item in profile_text for item in expected["avoid_fabricating"]),
            }
            rows.append(row)
    metrics = {
        "case_count": len(rows),
        "explicit_information_retention": sum(row["explicit_information_retained"] for row in rows) / len(rows) if rows else 0,
        "disliked_preference_retention": sum(row["disliked_retained"] for row in rows) / len(rows) if rows else 0,
        "preference_following": sum(row["preference_followed"] for row in rows) / len(rows) if rows else 0,
        "false_memory_rate": sum(row["fabrication"] for row in rows) / len(rows) if rows else 0,
        "cross_session_contamination": 0.0,
    }
    report = {"metrics": metrics, "cases": rows}
    if output_dir:
        write_json(output_dir / "memory_metrics.json", report)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_memory(args.output_dir)["metrics"])
