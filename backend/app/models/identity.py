import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Role(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    GESTOR = "GESTOR"
    SUPERVISOR = "SUPERVISOR"
    TECNICO = "TECNICO"
    MANUTENCAO = "MANUTENCAO"
    CLIENTE = "CLIENTE"


class CollaboratorGroup(str, enum.Enum):
    DIRETORIA = "DIRETORIA"
    BACKOFFICE = "BACKOFFICE"
    TECNICO = "TECNICO"


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    # Senha provisoria definida por um administrador: o usuario precisa troca-la para usar o app.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Collaborator(TimestampMixin, Base):
    """Pessoa que trabalha na empresa. A credencial de acesso e opcional."""

    __tablename__ = "collaborators"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document", name="uq_collaborators_tenant_document"),
        UniqueConstraint("membership_id", name="uq_collaborators_membership"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    document: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_whatsapp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    membership_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
