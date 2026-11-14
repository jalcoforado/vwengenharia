from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.models.identity import (
    Collaborator,
    CollaboratorGroup,
    Membership,
    RefreshToken,
    Role,
    User,
)
from app.models.operations import Client, ClientMembershipAccess
from app.modules.auth.dependencies import AuthContext
from app.modules.core_registers.service import add_audit
from app.modules.team.schemas import (
    AccessRead,
    CollaboratorCreate,
    CollaboratorCredentialCreate,
    CollaboratorRead,
    CollaboratorUpdate,
    TeamMemberCreate,
    TeamMemberUpdate,
)


def _can_manage_role(actor_role: str, target_role: str) -> bool:
    if target_role == Role.SUPERADMIN.value:
        return actor_role == Role.SUPERADMIN.value
    return actor_role in {Role.SUPERADMIN.value, Role.ADMIN.value}


async def list_team_members(
    session: AsyncSession,
    context: AuthContext,
    *,
    active_only: bool = False,
    roles: set[str] | None = None,
) -> list[Membership]:
    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.tenant_id == context.tenant.id)
    )
    if active_only:
        stmt = stmt.where(Membership.is_active.is_(True))
    if roles:
        stmt = stmt.where(Membership.role.in_(roles))
    stmt = stmt.order_by(User.name)
    return list((await session.execute(stmt.join(User))).scalars().all())


async def create_team_member(
    session: AsyncSession,
    context: AuthContext,
    payload: TeamMemberCreate,
    *,
    allow_client_role: bool = False,
) -> Membership:
    role = payload.role.value
    if not _can_manage_role(context.membership.role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_assign_role",
        )
    if role == Role.CLIENTE.value and not allow_client_role:
        # Login de portal nasce do cadastro do responsavel.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_credential_requires_responsible",
        )

    collaborator = None
    if payload.collaborator_id is not None:
        if role == Role.CLIENTE.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="collaborator_cannot_have_client_role",
            )
        collaborator = await _get_collaborator(session, context, payload.collaborator_id)
        if not collaborator.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="collaborator_inactive",
            )
        if collaborator.membership_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="collaborator_already_has_credential",
            )

    email = str(payload.email).lower().strip()
    existing_user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email_already_registered",
        )

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
        # A senha inicial e escolhida por quem cria o acesso: vale so ate o primeiro login.
        must_change_password=True,
    )
    session.add(user)
    await session.flush()

    membership = Membership(
        tenant_id=context.tenant.id,
        user_id=user.id,
        role=role,
        is_active=True,
    )
    session.add(membership)
    await session.flush()

    if collaborator is not None:
        collaborator.membership_id = membership.id
    else:
        # Sem colaborador informado, a credencial interna registra o seu.
        await ensure_collaborator_for_membership(session, membership, user)

    add_audit(
        session,
        context,
        action="TEAM_MEMBER_CREATE",
        entity_type="membership",
        entity_id=membership.id,
        fields=["email", "name", "role"],
    )
    await session.commit()

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.id == membership.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def update_team_member(
    session: AsyncSession,
    context: AuthContext,
    membership_id: UUID,
    payload: TeamMemberUpdate,
) -> Membership:
    membership = (
        await session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(
                Membership.id == membership_id,
                Membership.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member_not_found")

    if membership.role == Role.SUPERADMIN.value and context.membership.role != Role.SUPERADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_manage_superadmin",
        )

    changes = payload.model_dump(exclude_unset=True)
    if membership.id == context.membership.id and (
        "role" in changes or changes.get("is_active") is False
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot_change_own_membership",
        )

    if "role" in changes:
        role = changes["role"]
        new_role = role.value if isinstance(role, Role) else role
        # Portal e equipe sao mundos separados: o perfil CLIENTE nao e trocado por um interno.
        if (new_role == Role.CLIENTE.value) != (membership.role == Role.CLIENTE.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="client_role_is_fixed",
            )
        if isinstance(role, Role):
            role = role.value
        if not _can_manage_role(context.membership.role, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_assign_role",
            )
        membership.role = role

    if "is_active" in changes:
        if changes["is_active"]:
            inactive_collaborator = (
                await session.execute(
                    select(Collaborator.id).where(
                        Collaborator.membership_id == membership.id,
                        Collaborator.is_active.is_(False),
                    )
                )
            ).first()
            if inactive_collaborator is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="collaborator_inactive",
                )
        membership.is_active = bool(changes["is_active"])

    add_audit(
        session,
        context,
        action="TEAM_MEMBER_UPDATE",
        entity_type="membership",
        entity_id=membership.id,
        fields=sorted(changes.keys()),
    )
    await session.commit()
    await session.refresh(membership)
    return membership


async def change_own_password(
    session: AsyncSession,
    context: AuthContext,
    *,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, context.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_password_invalid",
        )
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="new_password_must_differ",
        )

    context.user.password_hash = hash_password(new_password)
    context.user.must_change_password = False
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == context.user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    add_audit(
        session,
        context,
        action="PASSWORD_CHANGE",
        entity_type="user",
        entity_id=context.user.id,
        fields=["password_hash"],
    )
    await session.commit()
def default_collaborator_category(role: str) -> str:
    if role in {Role.TECNICO.value, Role.MANUTENCAO.value}:
        return CollaboratorGroup.TECNICO.value
    return CollaboratorGroup.BACKOFFICE.value


async def ensure_collaborator_for_membership(
    session: AsyncSession,
    membership: Membership,
    user: User,
) -> Collaborator | None:
    """Toda credencial interna pertence a um colaborador (seed, bootstrap e API)."""
    if membership.role == Role.CLIENTE.value:
        return None
    collaborator = (
        await session.execute(
            select(Collaborator).where(Collaborator.membership_id == membership.id)
        )
    ).scalar_one_or_none()
    if collaborator is None:
        collaborator = Collaborator(
            tenant_id=membership.tenant_id,
            name=user.name,
            contact_email=user.email,
            category=default_collaborator_category(membership.role),
            membership_id=membership.id,
        )
        session.add(collaborator)
        await session.flush()
    return collaborator


async def _get_collaborator(
    session: AsyncSession,
    context: AuthContext,
    collaborator_id: UUID,
) -> Collaborator:
    collaborator = (
        await session.execute(
            select(Collaborator).where(
                Collaborator.id == collaborator_id,
                Collaborator.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if collaborator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="collaborator_not_found",
        )
    return collaborator


async def _ensure_collaborator_document_is_unique(
    session: AsyncSession,
    context: AuthContext,
    document: str | None,
    *,
    ignore_id: UUID | None = None,
) -> None:
    if not document:
        return
    stmt = select(Collaborator.id).where(
        Collaborator.tenant_id == context.tenant.id,
        Collaborator.document == document,
    )
    if ignore_id is not None:
        stmt = stmt.where(Collaborator.id != ignore_id)
    if (await session.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="collaborator_document_already_exists",
        )


async def _collaborator_rows(session: AsyncSession, context: AuthContext, *filters):
    stmt = (
        select(Collaborator, Membership, User)
        .outerjoin(Membership, Membership.id == Collaborator.membership_id)
        .outerjoin(User, User.id == Membership.user_id)
        .where(Collaborator.tenant_id == context.tenant.id, *filters)
        .order_by(Collaborator.name)
    )
    return (await session.execute(stmt)).all()


def collaborator_to_read(collaborator: Collaborator, membership, user) -> CollaboratorRead:
    return CollaboratorRead(
        id=collaborator.id,
        name=collaborator.name,
        document=collaborator.document,
        category=collaborator.category,
        contact_phone=collaborator.contact_phone,
        contact_whatsapp=collaborator.contact_whatsapp,
        contact_email=collaborator.contact_email,
        is_active=collaborator.is_active,
        membership_id=membership.id if membership else None,
        credential_email=user.email if user else None,
        credential_role=membership.role if membership else None,
        credential_active=membership.is_active if membership else None,
    )


async def list_collaborators(
    session: AsyncSession,
    context: AuthContext,
) -> list[CollaboratorRead]:
    return [
        collaborator_to_read(*row) for row in await _collaborator_rows(session, context)
    ]


async def read_collaborator(
    session: AsyncSession,
    context: AuthContext,
    collaborator_id: UUID,
) -> CollaboratorRead:
    rows = await _collaborator_rows(session, context, Collaborator.id == collaborator_id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="collaborator_not_found",
        )
    return collaborator_to_read(*rows[0])


async def create_collaborator(
    session: AsyncSession,
    context: AuthContext,
    payload: CollaboratorCreate,
) -> CollaboratorRead:
    await _ensure_collaborator_document_is_unique(session, context, payload.document)
    data = payload.model_dump()
    data["category"] = payload.category.value
    collaborator = Collaborator(tenant_id=context.tenant.id, **data)
    session.add(collaborator)
    await session.flush()
    add_audit(
        session,
        context,
        action="COLLABORATOR_CREATE",
        entity_type="collaborator",
        entity_id=collaborator.id,
    )
    await session.commit()
    return await read_collaborator(session, context, collaborator.id)


async def update_collaborator(
    session: AsyncSession,
    context: AuthContext,
    collaborator_id: UUID,
    payload: CollaboratorUpdate,
) -> CollaboratorRead:
    collaborator = await _get_collaborator(session, context, collaborator_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("category") is not None:
        changes["category"] = changes["category"].value
    await _ensure_collaborator_document_is_unique(
        session, context, changes.get("document"), ignore_id=collaborator.id
    )

    if changes.get("is_active") is False and collaborator.membership_id is not None:
        if collaborator.membership_id == context.membership.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot_change_own_membership",
            )
        membership = (
            await session.execute(
                select(Membership).where(Membership.id == collaborator.membership_id)
            )
        ).scalar_one()
        if (
            membership.role == Role.SUPERADMIN.value
            and context.membership.role != Role.SUPERADMIN.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="cannot_manage_superadmin",
            )
        # Colaborador inativo nao entra no app: bloqueia a credencial e as sessoes abertas.
        membership.is_active = False
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == membership.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    for field, value in changes.items():
        setattr(collaborator, field, value)
    if changes:
        add_audit(
            session,
            context,
            action="COLLABORATOR_UPDATE",
            entity_type="collaborator",
            entity_id=collaborator.id,
            fields=sorted(changes),
        )
        await session.commit()
    return await read_collaborator(session, context, collaborator.id)


async def create_collaborator_credential(
    session: AsyncSession,
    context: AuthContext,
    collaborator_id: UUID,
    payload: CollaboratorCredentialCreate,
) -> CollaboratorRead:
    collaborator = await _get_collaborator(session, context, collaborator_id)
    await create_team_member(
        session,
        context,
        TeamMemberCreate(
            email=payload.email,
            name=collaborator.name,
            password=payload.password,
            role=payload.role,
            collaborator_id=collaborator.id,
        ),
    )
    return await read_collaborator(session, context, collaborator.id)
async def reset_member_password(
    session: AsyncSession,
    context: AuthContext,
    membership_id: UUID,
    new_password: str,
) -> None:
    """O administrador define uma senha provisoria; a pessoa troca no proximo acesso."""
    membership = (
        await session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(
                Membership.id == membership_id,
                Membership.tenant_id == context.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member_not_found")
    if membership.id == context.membership.id:
        # A propria senha se troca informando a atual, em /auth/change-password.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot_change_own_membership",
        )
    if membership.role == Role.SUPERADMIN.value and context.membership.role != Role.SUPERADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_manage_superadmin",
        )

    membership.user.password_hash = hash_password(new_password)
    membership.user.must_change_password = True
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == membership.user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    add_audit(
        session,
        context,
        action="PASSWORD_RESET",
        entity_type="user",
        entity_id=membership.user_id,
        fields=["password_hash"],
    )
    await session.commit()


async def list_accesses(session: AsyncSession, context: AuthContext) -> list[AccessRead]:
    """Todos os logins do tenant: equipe (colaboradores) e portal (responsaveis)."""
    rows = (
        await session.execute(
            select(Membership, User, Collaborator)
            .join(User, User.id == Membership.user_id)
            .outerjoin(Collaborator, Collaborator.membership_id == Membership.id)
            .where(Membership.tenant_id == context.tenant.id)
            .order_by(User.name)
        )
    ).all()
    portal_links = {
        membership_id: client
        for membership_id, client in (
            await session.execute(
                select(ClientMembershipAccess.membership_id, Client)
                .join(Client, Client.id == ClientMembershipAccess.client_id)
                .where(ClientMembershipAccess.tenant_id == context.tenant.id)
                .order_by(ClientMembershipAccess.created_at.desc())
            )
        ).all()
    }

    accesses = []
    for membership, user, collaborator in rows:
        client = portal_links.get(membership.id)
        if collaborator is not None:
            kind, linked = "COLLABORATOR", collaborator
        elif client is not None:
            kind, linked = "RESPONSIBLE", client
        else:
            kind, linked = "UNLINKED", None
        accesses.append(
            AccessRead(
                membership_id=membership.id,
                user_id=user.id,
                name=user.name,
                email=user.email,
                role=membership.role,
                is_active=membership.is_active and user.is_active,
                must_change_password=user.must_change_password,
                kind=kind,
                linked_id=linked.id if linked else None,
                linked_name=linked.name if linked else None,
                linked_active=linked.is_active if linked else None,
            )
        )
    return accesses
