from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator
from sqlalchemy.orm import DeclarativeBase
from config import config

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
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
        
class Base(DeclarativeBase):
    pass

