from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ChatSessionCreate(BaseModel):
    course_id: int


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    image: str | None = None
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
    content: str = Field(default="", max_length=8000)
    session_id: int | None = None
    image_data: str | None = Field(
        default=None,
        max_length=15_000_000,
        description="Base64 data URL of an attached image (e.g. 'data:image/png;base64,...').",
    )

    @model_validator(mode="after")
    def _require_content_or_image(self) -> "SendMessageRequest":
        """Allow image-only messages, but reject a completely empty message."""
        if not self.content.strip() and not self.image_data:
            raise ValueError("پیام نمی‌تواند خالی باشد. متن یا تصویر ارسال کنید.")
        return self
