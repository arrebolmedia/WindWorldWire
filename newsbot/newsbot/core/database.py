"""Database configuration and utilities."""
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .settings import settings

# SQLAlchemy base for models
Base = declarative_base()

# Sync engine for migrations and testing
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.database_echo,
    pool_size=10,
    max_overflow=20,
)

# Async engine for application
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=10,
    max_overflow=20,
)

# Session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
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


def create_tables():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=sync_engine)


def drop_tables():
    """Drop all tables in the database."""
    Base.metadata.drop_all(bind=sync_engine)