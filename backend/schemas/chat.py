from typing import Any, Literal

from pydantic import BaseModel, Field


class CheckIn(BaseModel):
    stress_score: int | None = Field(default=None, ge=0, le=10)
    stress_source: list[str] = Field(default_factory=list)
    stress_sources: list[str] = Field(default_factory=list)
    preferred_style: str | None = None

    def normalized_sources(self) -> list[str]:
        return self.stress_sources or self.stress_source


class FaceEmotion(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    checkin: CheckIn | None = None
    face_emotion: FaceEmotion | None = None


class MultimodalChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = ""
    file_ids: list[str] = Field(default_factory=list)
    checkin: CheckIn | None = None


class MultimodalChatResponse(BaseModel):
    session_id: str
    message_id: str
    input_modalities: list[str]
    attachments: list[dict[str, Any]]
    transcript: dict[str, Any]
    media_analysis: dict[str, Any]
    emotion: dict[str, Any]
    risk: dict[str, Any]
    reply: str
    interventions: list[dict[str, Any]]
    agent_trace: list[dict[str, str]]
    provider_metadata: dict[str, Any]
    knowledge_sources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    psychological_state: dict[str, Any] = Field(default_factory=dict)
    strategy_plan: dict[str, Any] = Field(default_factory=dict)
    rag_route: dict[str, Any] = Field(default_factory=dict)
    request_metrics: dict[str, Any] = Field(default_factory=dict)
