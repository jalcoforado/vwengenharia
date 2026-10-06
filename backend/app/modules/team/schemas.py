from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.identity import Role


class TeamMemberCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    role: Role


class TeamMemberUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class TeamMemberRead(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: EmailStr
    name: str
    role: str
    is_active: bool


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
