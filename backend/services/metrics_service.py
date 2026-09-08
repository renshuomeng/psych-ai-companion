import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from database.models import RequestMetric


def estimate_cost(token_usage: dict[str, Any] | None) -> dict[str, Any]:
    settings = get_settings()
    usage = token_usage or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if (
        input_tokens is None
        or output_tokens is None
        or settings.doubao_input_price_per_1k is None
        or settings.doubao_output_price_per_1k is None
    ):
        return {
            "currency": settings.cost_currency,
            "amount": None,
            "calculation_status": "unknown",
        }
    amount = (float(input_tokens) / 1000) * settings.doubao_input_price_per_1k + (
        float(output_tokens) / 1000
    ) * settings.doubao_output_price_per_1k
    return {
        "currency": settings.cost_currency,
        "amount": round(amount, 6),
        "calculation_status": "configured",
    }


def record_request_metric(
    db: Session,
    session_id: str,
    route: str,
    total_duration_ms: int,
    stages: dict[str, int] | None = None,
    token_usage: dict[str, Any] | None = None,
    provider: str = "",
    model: str = "",
    request_id: str = "",
    success: bool = True,
) -> dict[str, Any]:
    cost = estimate_cost(token_usage)
    metric = RequestMetric(
        metric_id=uuid.uuid4().hex,
        session_id=session_id,
        request_id=request_id or uuid.uuid4().hex,
        route=route,
        total_duration_ms=total_duration_ms,
        stages_json=json.dumps(stages or {}, ensure_ascii=False, sort_keys=True),
        token_usage_json=json.dumps(token_usage or {"status": "unknown"}, ensure_ascii=False, sort_keys=True),
        estimated_cost_json=json.dumps(cost, ensure_ascii=False, sort_keys=True),
        provider=provider,
        model=model,
        success=success,
    )
    db.add(metric)
    db.commit()
    return {
        "total_duration_ms": total_duration_ms,
        "stages": stages or {},
        "token_usage": token_usage or {"status": "unknown"},
        "estimated_cost": cost,
    }
