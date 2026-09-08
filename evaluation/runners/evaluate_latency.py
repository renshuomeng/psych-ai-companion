import json
from pathlib import Path
from typing import Any

from evaluation.metrics.cost_metrics import latency_cost_report
from evaluation.runners.common import write_json

from database.db import SessionLocal, init_db
from database.models import RequestMetric


def evaluate_latency(output_dir: Path | None = None) -> dict[str, Any]:
    init_db()
    with SessionLocal() as db:
        rows = db.query(RequestMetric).order_by(RequestMetric.created_at.desc()).limit(500).all()
        metrics = [
            {
                "total_duration_ms": row.total_duration_ms,
                "success": row.success,
                "token_usage": json.loads(row.token_usage_json or "{}"),
                "estimated_cost": json.loads(row.estimated_cost_json or "{}"),
            }
            for row in rows
        ]
    report = {"metrics": latency_cost_report(metrics), "sample_size": len(metrics)}
    if output_dir:
        write_json(output_dir / "latency_metrics.json", report)
        write_json(output_dir / "cost_metrics.json", {"metrics": report["metrics"]})
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_latency(args.output_dir)["metrics"])
