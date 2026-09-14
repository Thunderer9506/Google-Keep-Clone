from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager

from models import User
from db import engine, Base, get_db_session

from routes.auth import auth_router, get_user

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

app.include_router(auth_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Google Keep Clone API!"}

@app.get("/users")
async def get_current_user(current_user = Depends(get_user)):
    return {"username": current_user["username"], "hashed_password": current_user["password"]}