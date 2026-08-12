from datetime import datetime

from pydantic import BaseModel, Field


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CourseCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class CourseUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None