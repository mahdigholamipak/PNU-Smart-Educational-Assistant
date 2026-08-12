from datetime import datetime

from pydantic import BaseModel


class ResourceResponse(BaseModel):
    id: int
    course_id: int
    course_title: str | None = None
    filename: str
    status: str
    chunk_count: int
    uploaded_at: datetime | None = None

    model_config = {"from_attributes": True}


class SettingResponse(BaseModel):
    key: str
    value: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SettingUpdateRequest(BaseModel):
    value: str | None = None