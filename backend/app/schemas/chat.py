from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    course_id: int


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id: int
    course_id: int
    course_title: str | None = None
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse] = []


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)