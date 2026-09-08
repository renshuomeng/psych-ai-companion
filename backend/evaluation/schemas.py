from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


FrameworkId = Literal["care_bench", "esc_eval", "cpsycoun", "counselbench"]
SystemId = Literal[
    "direct_doubao",
    "full_agent",
    "agent_without_rag",
    "agent_without_strategy",
    "agent_without_psychological_state",
    "custom_agent",
]


@dataclass(slots=True)
class AblationConfig:
    risk: bool = True
    psychological_state: bool = True
    strategy: bool = True
    rag: bool = True
    safety: bool = True

    @classmethod
    def for_system(cls, system_id: str, custom: dict[str, Any] | None = None) -> "AblationConfig":
        if system_id == "direct_doubao":
            return cls(risk=False, psychological_state=False, strategy=False, rag=False, safety=False)
        if system_id == "agent_without_rag":
            return cls(rag=False)
        if system_id == "agent_without_strategy":
            return cls(strategy=False)
        if system_id == "agent_without_psychological_state":
            return cls(psychological_state=False)
        if system_id == "custom_agent" and custom:
            base = cls()
            for key in ["risk", "psychological_state", "strategy", "rag", "safety"]:
                if key in custom:
                    setattr(base, key, bool(custom[key]))
            return base
        return cls()

    def model_dump(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(slots=True)
class EvaluationCase:
    case_id: str
    dataset: str
    turns: list[str]
    tags: list[str] = field(default_factory=list)
    expected: dict[str, Any] = field(default_factory=dict)
    reference_notes: str = ""

    @property
    def first_turn(self) -> str:
        return self.turns[0] if self.turns else ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandidateResult:
    system_id: str
    response: str
    latency_ms: int
    risk: dict[str, Any] = field(default_factory=dict)
    emotion: dict[str, Any] = field(default_factory=dict)
    psychological_state: dict[str, Any] = field(default_factory=dict)
    strategy_plan: dict[str, Any] = field(default_factory=dict)
    rag_route: dict[str, Any] = field(default_factory=dict)
    knowledge_sources: list[dict[str, Any]] = field(default_factory=list)
    interventions: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any] | str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MetricScore:
    framework_id: str
    metric_name: str
    score: float
    scale_min: float
    scale_max: float
    direction: str
    implementation_status: str
    scorer: str
    rationale: str = ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunConfig:
    system_id: str = "full_agent"
    frameworks: list[str] = field(default_factory=lambda: ["care_bench", "esc_eval", "cpsycoun", "counselbench"])
    limit: int = 5
    dry_run: bool = False
    resume_run_id: str | None = None
    ablation: AblationConfig = field(default_factory=AblationConfig)
    dataset_name: str = "competition_smoke_v1"
    benchmark_pack: str | None = None
    use_cache: bool = True

    def model_dump(self) -> dict[str, Any]:
        data = asdict(self)
        data["ablation"] = self.ablation.model_dump()
        return data
