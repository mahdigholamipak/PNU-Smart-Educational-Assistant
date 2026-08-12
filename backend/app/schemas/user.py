from pydantic import BaseModel, EmailStr, Field


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    student_id: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=20)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PublicUserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    student_id: str | None = None
    phone: str | None = None
    role: str
    is_active: bool
    created_at: object | None = None

    model_config = {"from_attributes": True}