from uuid import uuid4

import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    encoded = hash_password("senha-segura-123")
    assert encoded != "senha-segura-123"
    assert verify_password("senha-segura-123", encoded)
    assert not verify_password("senha-errada", encoded)


def test_access_token_carries_tenant_membership_and_role() -> None:
    user_id = uuid4()
    membership_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(
        user_id=user_id,
        membership_id=membership_id,
        tenant_id=tenant_id,
        role="TECNICO",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["membership_id"] == str(membership_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["role"] == "TECNICO"
    assert payload["type"] == "access"


def test_access_token_rejects_wrong_type() -> None:
    from app.core.config import settings

    bad_token = jwt.encode(
        {"sub": str(uuid4()), "type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    try:
        decode_access_token(bad_token)
    except jwt.InvalidTokenError:
        pass
    else:
        raise AssertionError("refresh token type must not be accepted as access token")


def test_refresh_tokens_are_random_and_only_hash_is_storable() -> None:
    first = new_refresh_token()
    second = new_refresh_token()
    assert first != second
    assert len(first) >= 32
    assert len(hash_refresh_token(first)) == 64
    assert hash_refresh_token(first) != first
