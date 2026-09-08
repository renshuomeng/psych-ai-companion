from pydantic import BaseModel, Field

from schemas.chat import CheckIn


class MultimodalJobCreateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = ""
    file_ids: list[str] = Field(default_factory=list)
    checkin: CheckIn | None = None


class JobResponse(BaseModel):
    job_id: str
    session_id: str
    status: str
    stage: str
    progress: int = 0
    result: dict | None = None
    error: dict | None = None
