"""Async database engine and session management.

REQ-005 §2.2: Configures SQLAlchemy async engine with connection pooling
and provides dependency injection for database sessions.

Coordinates with:
  - core/config.py — imports settings for database_url and environment

Called by: main.py (async_session_factory for lifespan), api/deps.py (get_db
for endpoint dependency injection).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
