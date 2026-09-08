from statistics import median
from typing import Any


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[index]


def latency_cost_report(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [int(item.get("total_duration_ms", 0)) for item in metrics]
    return {
        "request_count": len(metrics),
        "average_latency_ms": round(sum(durations) / len(durations), 2) if durations else 0,
        "p50_latency_ms": int(median(durations)) if durations else 0,
        "p95_latency_ms": percentile(durations, 0.95),
        "success_rate": sum(1 for item in metrics if item.get("success", True)) / len(metrics)
        if metrics
        else 0,
        "cost_status": "unknown_without_price_config" if metrics else "no_metrics",
    }
