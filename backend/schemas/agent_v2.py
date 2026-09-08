from typing import Any, Literal

from pydantic import BaseModel, Field


EmotionLabel = Literal[
    "anxiety",
    "sadness",
    "anger",
    "frustration",
    "loneliness",
    "shame",
    "guilt",
    "fatigue",
    "stress",
    "calm",
    "neutral",
    "mixed",
    "unknown",
]

CauseCategory = Literal[
    "academic",
    "thesis",
    "research",
    "exam",
    "employment",
    "interpersonal",
    "romantic_relationship",
    "roommate",
    "family",
    "financial",
    "sleep",
    "health",
    "self_evaluation",
    "future_uncertainty",
    "loneliness",
    "other",
    "unknown",
]

NeedLabel = Literal[
    "emotional_validation",
    "being_heard",
    "clarity",
    "sense_of_control",
    "problem_solving",
    "information",
    "encouragement",
    "social_connection",
    "rest",
    "self_compassion",
    "safety",
    "unknown",
]

StageLabel = Literal[
    "relationship_building",
    "exploration",
    "emotion_clarification",
    "cause_exploration",
    "goal_setting",
    "intervention",
    "follow_up",
    "closure",
    "unknown",
]

StrategyLabel = Literal[
    "reflection",
    "restatement",
    "emotional_validation",
    "clarification",
    "open_question",
    "affirmation",
    "information",
    "problem_solving",
    "cognitive_reappraisal",
    "behavioral_activation",
    "grounding",
    "self_compassion",
    "referral",
    "supportive_presence",
]


class PsychologicalEmotion(BaseModel):
    primary: EmotionLabel = "unknown"
    secondary: list[EmotionLabel] = Field(default_factory=list, max_length=3)
    intensity: float = Field(default=0.0, ge=0, le=1)
    valence: float = Field(default=0.0, ge=-1, le=1)
    arousal: float = Field(default=0.0, ge=0, le=1)
    control: float = Field(default=0.5, ge=0, le=1)


class PsychologicalCause(BaseModel):
    category: CauseCategory = "unknown"
    specific: str = ""
    evidence_terms: list[str] = Field(default_factory=list)


class PsychologicalState(BaseModel):
    schema_version: str = "agent_v2.psychological_state.v1"
    emotion: PsychologicalEmotion = Field(default_factory=PsychologicalEmotion)
    cause: PsychologicalCause = Field(default_factory=PsychologicalCause)
    needs: list[NeedLabel] = Field(default_factory=lambda: ["unknown"])
    stage: StageLabel = "unknown"
    information_gaps: list[str] = Field(default_factory=list, max_length=3)
    confidence: float = Field(default=0.0, ge=0, le=1)
    uncertainty_reason: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    method: str = "local_rules"


class StrategyPlan(BaseModel):
    schema_version: str = "agent_v2.strategy_plan.v1"
    primary_strategy: StrategyLabel = "supportive_presence"
    secondary_strategy: list[StrategyLabel] = Field(default_factory=list, max_length=4)
    should_give_advice: bool = False
    should_ask_question: bool = True
    should_use_rag: bool = False
    response_constraints: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class RAGRoute(BaseModel):
    schema_version: str = "agent_v2.rag_route.v1"
    should_retrieve: bool = False
    collections: list[str] = Field(default_factory=list)
    query: str = ""
    metadata_filter: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=3, ge=1, le=6)
    reason_codes: list[str] = Field(default_factory=list)
    fallback: str = "no_rag"
