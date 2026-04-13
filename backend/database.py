# backend/database.py — Async SQLAlchemy engine + session management
"""
Database connection layer using async SQLAlchemy with PostGIS support.
Provides session factory and dependency injection for FastAPI routes.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from config import settings


# ── Async Engine ─────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# ── Session Factory ──────────────────────────────────────────────────
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base Model ───────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


# ── Dependency ───────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency: yields a database session per request."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Init/Teardown ────────────────────────────────────────────────────
async def init_db():
    """Create all tables (dev only — use Alembic in production)."""
    async with engine.begin() as conn:
        # Enable PostGIS extension
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS postgis;")
        )
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose engine connections on shutdown."""
    await engine.dispose()
