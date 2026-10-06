from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


@lru_cache
def get_engine() -> AsyncEngine:
    kwargs: dict = {"pool_pre_ping": True}
    if settings.app_env.lower() == "test":
        kwargs["poolclass"] = NullPool
        kwargs.pop("pool_pre_ping")
    return create_async_engine(settings.database_url, **kwargs)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
