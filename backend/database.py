"""
Database connection and session management.
Uses SQLAlchemy with asyncpg for async PostgreSQL operations.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import settings

# SQLAlchemy async engine
engine = create_async_engine(
    settings.database_url, echo=settings.debug, pool_pre_ping=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


# Base class for ORM models 
class Base(DeclarativeBase):
    pass


# Dependency for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Usage:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Database lifecycle management
async def close_db():
    """Close database connections."""
    await engine.dispose()
