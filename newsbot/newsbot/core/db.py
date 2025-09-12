"""Database module with async SQLAlchemy engine and session management."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from .settings import get_settings

settings = get_settings()

# SQLAlchemy base for models
Base = declarative_base()

# Async engine
async_engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database connection."""
    # Test connection
    async with async_engine.begin() as conn:
        # This will test the connection
        await conn.execute("SELECT 1")


async def create_all():
    """Create all tables in the database."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all():
    """Drop all tables in the database."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)