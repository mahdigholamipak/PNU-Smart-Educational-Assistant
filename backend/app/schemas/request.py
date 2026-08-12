from datetime import datetime

from pydantic import BaseModel, Field


class CourseRequestCreate(BaseModel):
    course_name: str = Field(min_length=1, max_length=255)
    course_code: str | None = Field(default=None, max_length=50)
    description: str | None = None


class CourseRequestResponse(BaseModel):
    id: int
    course_name: str
    course_code: str | None = None
    description: str | None = None
    status: str
    admin_note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CourseRequestAdminUpdate(BaseModel):
    status: str = Field(pattern="^(pending|approved|rejected)$")
    admin_note: str | None = None