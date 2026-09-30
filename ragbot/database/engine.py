"""SQLAlchemy async engine and session factory configuration."""

from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_async_postgres_url(url: str) -> str:
    """Return a SQLAlchemy asyncpg URL or reject non-PostgreSQL databases."""
    if not url or not url.strip():
        raise ValueError("PostgreSQL database URL is required")

    parsed = make_url(url.strip())
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("Phase 5 database runtime requires PostgreSQL")

    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+asyncpg")
    elif parsed.drivername != "postgresql+asyncpg":
        raise ValueError("PostgreSQL database URL must use the asyncpg driver")

    return parsed.render_as_string(hide_password=False)


class DatabaseRuntime:
    """Own the async engine and create one AsyncSession per unit of work."""

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        normalized_url = normalize_async_postgres_url(url)
        self.engine: AsyncEngine = create_async_engine(
            normalized_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
        )

    async def dispose(self) -> None:
        """Release all pooled database connections."""
        await self.engine.dispose()
