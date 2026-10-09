from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.models.identity import Role
from app.modules.auth.dependencies import AuthContext, SessionDep, require_roles
from app.modules.team.schemas import (
    ChangePasswordRequest,
    CollaboratorCreate,
    CollaboratorCredentialCreate,
    CollaboratorRead,
    CollaboratorUpdate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberUpdate,
)
from app.modules.team.service import (
    change_own_password,
    create_collaborator,
    create_collaborator_credential,
    create_team_member,
    list_collaborators,
    list_team_members,
    update_collaborator,
    update_team_member,
)

router = APIRouter(tags=["equipe"])

READ_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
    Role.GESTOR.value,
    Role.SUPERVISOR.value,
)
ADMIN_ROLES = (
    Role.SUPERADMIN.value,
    Role.ADMIN.value,
)

ReadContextDep = Annotated[AuthContext, Depends(require_roles(*READ_ROLES))]
AdminContextDep = Annotated[AuthContext, Depends(require_roles(*ADMIN_ROLES))]


def to_read(membership) -> TeamMemberRead:
    return TeamMemberRead(
        membership_id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        name=membership.user.name,
        role=membership.role,
        is_active=membership.is_active,
    )


@router.get("/team", response_model=list[TeamMemberRead])
async def get_team(
    context: ReadContextDep,
    session: SessionDep,
    active_only: bool = False,
    roles: Annotated[list[Role] | None, Query()] = None,
) -> list[TeamMemberRead]:
    role_values = {role.value for role in roles} if roles else None
    members = await list_team_members(
        session,
        context,
        active_only=active_only,
        roles=role_values,
    )
    return [to_read(member) for member in members]


@router.post(
    "/team",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_team_member(
    payload: TeamMemberCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> TeamMemberRead:
    return to_read(await create_team_member(session, context, payload))


@router.patch("/team/{membership_id}", response_model=TeamMemberRead)
async def patch_team_member(
    membership_id: UUID,
    payload: TeamMemberUpdate,
    context: AdminContextDep,
    session: SessionDep,
) -> TeamMemberRead:
    return to_read(
        await update_team_member(
            session,
            context,
            membership_id,
            payload,
        )
    )


@router.get("/collaborators", response_model=list[CollaboratorRead])
async def get_collaborators(
    context: ReadContextDep,
    session: SessionDep,
) -> list[CollaboratorRead]:
    return await list_collaborators(session, context)


@router.post(
    "/collaborators",
    response_model=CollaboratorRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_collaborator(
    payload: CollaboratorCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> CollaboratorRead:
    return await create_collaborator(session, context, payload)


@router.patch("/collaborators/{collaborator_id}", response_model=CollaboratorRead)
async def patch_collaborator(
    collaborator_id: UUID,
    payload: CollaboratorUpdate,
    context: AdminContextDep,
    session: SessionDep,
) -> CollaboratorRead:
    return await update_collaborator(session, context, collaborator_id, payload)


@router.post(
    "/collaborators/{collaborator_id}/credential",
    response_model=CollaboratorRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_collaborator_credential(
    collaborator_id: UUID,
    payload: CollaboratorCredentialCreate,
    context: AdminContextDep,
    session: SessionDep,
) -> CollaboratorRead:
    return await create_collaborator_credential(session, context, collaborator_id, payload)


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def post_change_password(
    payload: ChangePasswordRequest,
    context: Annotated[
        AuthContext,
        Depends(
            require_roles(
                Role.SUPERADMIN.value,
                Role.ADMIN.value,
                Role.GESTOR.value,
                Role.SUPERVISOR.value,
                Role.TECNICO.value,
                Role.MANUTENCAO.value,
                Role.CLIENTE.value,
            )
        ),
    ],
    session: SessionDep,
) -> Response:
    await change_own_password(
        session,
        context,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
