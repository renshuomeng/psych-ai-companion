from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from schemas.chat import CheckIn


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    is_archived: bool | None = None


class ConversationMessageCreateRequest(BaseModel):
    content: str = ""
    file_ids: list[str] = Field(default_factory=list)
    checkin: CheckIn | None = None
    client_message_id: str | None = Field(default=None, max_length=128)


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    is_archived: bool
    title_manually_set: bool
    last_message_preview: str = ""
    message_count: int = 0


class ConversationMessageResponse(BaseModel):
    id: str
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    sequence: int
    message_type: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationListResponse(BaseModel):
    items: list[ConversationSummaryResponse]
    next_cursor: str | None = None


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummaryResponse
    messages: list[ConversationMessageResponse]
    has_more_messages: bool = False


class ConversationSendResponse(BaseModel):
    conversation: ConversationSummaryResponse
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
    result: dict[str, Any]
