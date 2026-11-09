import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from typing import AsyncGenerator
from sqlalchemy.orm import DeclarativeBase
from app.config import config

logger = logging.getLogger("google_keep_clone_app.db")


class Base(DeclarativeBase):
    pass

engine = create_async_engine(config.DB_URL, echo=True)

async_session = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False  # Prevents unexpected lazy loading issues after commit
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async session.
    Automatically handles cleanup/closing after the request lifecycle.
    """
    try:
        async with async_session() as session:
            yield session
    except SQLAlchemyError:
        logger.exception("Database session failed")
        raise
        
