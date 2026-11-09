import logging
from app.logs import configure_logging

configure_logging()

from fastapi import FastAPI, status
from contextlib import asynccontextmanager

from app.db import engine, Base

from app.routes.auth import auth_router
from app.routes.notes import notes_router
from app.routes.tags import tags_router

logger = logging.getLogger("google_keep_clone_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        logger.exception("Application startup failed while initializing the database")
        raise
    logger.info("Database connected")
    yield

app = FastAPI(
    title="Google Keep Clone", 
    description="A clone of Google Keep built with FastAPI and Streamlit", 
    version="1.0.0",
    lifespan=lifespan)


app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(tags_router)

@app.get("/health", status_code=status.HTTP_200_OK)
async def root():
    logger.info("Health check requested")
    return {"message": "Welcome to the Google Keep Clone API!"}
