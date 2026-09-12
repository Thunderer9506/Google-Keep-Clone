from fastapi import FastAPI
from contextlib import asynccontextmanager
from models import User
from db import engine, Base
from sqlalchemy.orm import Session
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("⬆️ Database connected")
    yield

app = FastAPI(
    title="Google Keep Clone", 
    description="A clone of Google Keep built with FastAPI and Streamlit", 
    version="1.0.0",
    lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Welcome to the Google Keep Clone API!"}

@app.get("/test")
def test():
    with Session(engine) as session:
        result = session.execute(text('SELECT * FROM users')).scalar()
        return {"result": result}