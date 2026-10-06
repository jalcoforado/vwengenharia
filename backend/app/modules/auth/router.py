from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.modules.auth.dependencies import AuthContextDep
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    MeTenant,
    MeUser,
    RefreshRequest,
    TokenResponse,
)
from app.modules.auth.service import (
    authenticate,
    issue_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=settings.api_v1_prefix + "/auth",
    )


def public_token_response(tokens: TokenResponse) -> TokenResponse:
    if settings.is_production:
        return tokens.model_copy(update={"refresh_token": None})
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: SessionDep,
) -> TokenResponse:
    selection = await authenticate(
        session,
        email=str(payload.email),
        password=payload.password,
        tenant_id=payload.tenant_id,
    )
    tokens = await issue_tokens(
        session,
        user=selection.user,
        membership=selection.membership,
        audit_action="AUTH_LOGIN",
    )
    if tokens.refresh_token is None:
        raise RuntimeError("refresh token missing after issue")
    set_refresh_cookie(response, tokens.refresh_token)
    return public_token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    payload: RefreshRequest | None = None,
) -> TokenResponse:
    cookie_token = request.cookies.get(settings.refresh_cookie_name)
    body_token = payload.refresh_token if payload is not None else None
    raw_token = cookie_token if settings.is_production else (body_token or cookie_token)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_refresh_token",
        )

    tokens = await rotate_refresh_token(session, raw_token=raw_token)
    if tokens.refresh_token is None:
        raise RuntimeError("refresh token missing after rotation")
    set_refresh_cookie(response, tokens.refresh_token)
    return public_token_response(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
) -> Response:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        await revoke_refresh_token(session, raw_token=raw_token)
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.api_v1_prefix + "/auth",
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(context: AuthContextDep) -> MeResponse:
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
