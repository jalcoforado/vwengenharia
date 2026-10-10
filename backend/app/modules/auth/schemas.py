from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    tenant_id: UUID | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    tenant_id: UUID
    role: str


class MeUser(BaseModel):
    id: UUID
    email: EmailStr
    name: str


class MeTenant(BaseModel):
    id: UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    user: MeUser
    tenant: MeTenant
    membership_id: UUID
    role: str
    must_change_password: bool = False
