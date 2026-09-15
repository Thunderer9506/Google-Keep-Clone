import pytest

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.config import config
from app.db import get_db_session, Base

engine = create_async_engine(config.DB_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def db_session():
    # Connect to the database
    async with engine.connect() as connection:
        # Start a transaction block
        async with connection.begin() as transaction:
            async with TestingSessionLocal(bind=connection) as session:
                yield session
                # Once the test finishes execution, roll back all queries executed during the test
                await transaction.rollback()

# 2. Async HTTP Client that overrides FastAPI's internal database dependency
@pytest.fixture
async def async_client(db_session: AsyncSession):
    # Override FastAPI's database dependency to inject our rollback session
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
        
    # Clean up dependency overrides after the test finishes
    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/")
    
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Google Keep Clone API!"}

@pytest.mark.anyio
async def test_register_user_success(async_client: AsyncClient):
    payload = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    
    # 1. Make the POST request to your registration route
    response = await async_client.post("/auth/register", json=payload)
    response_data = response.json()
    
    # 2. Assertions
    assert response.status_code == 201
    assert response_data["username"] == "testuser"
    assert response_data["email"] == "testuser@example.com"
    assert response_data["message"] == "User registered successfully"
    assert "password" not in response_data  # Ensure password is not returned
    
    # When this function exits, the db_session fixture kicks in 
    # and completely rolls back "testuser@example.com" from the database.