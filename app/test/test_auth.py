from fastapi.testclient import TestClient
import asyncio
import pytest
from app.main import app
from app.db import get_db_session, Base
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

client = TestClient(app)
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, poolclass=StaticPool)

TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def override_get_db_session():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        await db.close()

app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.fixture(autouse=True)
def setup_database():
    async def create_tables():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    yield

    async def drop_tables():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

    asyncio.run(drop_tables())


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Google Keep Clone API!"}

def test_register_route():
    payload = {
        "username": "Testuser",
        "email": "testuser@example.com",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["message"] == "User registered successfully"
    assert response.json()["username"] == "Testuser"
    assert response.json()["email"] == "testuser@example.com"

def test_login_route():
    payload = {
        "username": "Testuser",
        "email": "testuser@example.com",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "Bearer"