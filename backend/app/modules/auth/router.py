from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.dependencies import AuthContext, get_auth_context
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    MeTenant,
    MeUser,
    RefreshRequest,
    TokenResponse,
)
from app.modules.auth.service import authenticate, issue_tokens, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    selection = await authenticate(
        session,
        email=str(payload.email),
        password=payload.password,
        tenant_id=payload.tenant_id,
    )
    return await issue_tokens(
        session,
        user=selection.user,
        membership=selection.membership,
        audit_action="AUTH_LOGIN",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    return await rotate_refresh_token(session, raw_token=payload.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(context: AuthContext = Depends(get_auth_context)) -> MeResponse:
    return MeResponse(
        user=MeUser(id=context.user.id, email=context.user.email, name=context.user.name),
        tenant=MeTenant(
            id=context.tenant.id,
            name=context.tenant.name,
            slug=context.tenant.slug,
        ),
        membership_id=context.membership.id,
        role=context.membership.role,
    )
