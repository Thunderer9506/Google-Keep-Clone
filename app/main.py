from fastapi import Depends, FastAPI
from contextlib import asynccontextmanager

from models import User
from db import engine, Base, get_db_session

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("⬆️ Database connected")
    yield

app = FastAPI(
    title="Google Keep Clone", 
    description="A clone of Google Keep built with FastAPI and Streamlit", 
    version="1.0.0",
    lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Google Keep Clone API!"}

@app.get("/test")
async def test(db: AsyncSession = Depends(get_db_session)):
    query_result = await db.execute(select(User).limit(1))
    user = query_result.scalars().first()
    if user:
        return {"result": {"id": user.id, "email": getattr(user, "email", "N/A")}}
    return {"result": user}