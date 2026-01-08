"""Database configuration and session management"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from typing import AsyncGenerator
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            logger.warning(f"Database integrity error: {e}")
            await session.rollback()
            raise
        except OperationalError as e:
            logger.error(f"Database operational error: {e}")
            await session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error during database operation: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()


def get_sync_db():
    """Get synchronous database session for Celery tasks"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Convert async URL to sync URL
    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    sync_engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

    return SessionLocal()
