from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from config import get_settings
from .schemas import AblationConfig


@contextmanager
def temporary_ablation(ablation: AblationConfig) -> Iterator[None]:
    settings = get_settings()
    keys = {
        "psychological_state_analyzer_enabled": ablation.psychological_state,
        "strategy_planner_enabled": ablation.strategy,
        "rag_router_enabled": ablation.rag,
        "rag_enabled": ablation.rag,
        "rag_v1_enabled": ablation.rag,
    }
    original: dict[str, Any] = {key: getattr(settings, key) for key in keys}
    try:
        for key, value in keys.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
