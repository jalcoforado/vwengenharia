from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.identity import CollaboratorGroup, Role


class TeamMemberCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    role: Role
    collaborator_id: UUID | None = None


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


class CollaboratorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    document: str | None = Field(default=None, max_length=32)
    category: CollaboratorGroup
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_whatsapp: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None


class CollaboratorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    document: str | None = Field(default=None, max_length=32)
    category: CollaboratorGroup | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_whatsapp: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    is_active: bool | None = None


class CollaboratorRead(BaseModel):
    id: UUID
    name: str
    document: str | None
    category: str
    contact_phone: str | None
    contact_whatsapp: str | None
    contact_email: str | None
    is_active: bool
    membership_id: UUID | None
    credential_email: str | None
    credential_role: str | None
    credential_active: bool | None


class CollaboratorCredentialCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: Role
