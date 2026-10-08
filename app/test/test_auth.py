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

# ----------------------- Manual Tests -----------------------

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

def test_me_route():
    payload = {
        "username": "Testuser",
        "email": "testuser@example.com",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 200

    response = client.get("/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert response.status_code == 200
    assert response.json()["username"] == "Testuser"
    assert response.json()["email"] == "testuser@example.com"
    assert "id" in response.json()

# ----------------------- Register Route Test Cases -----------------------


# Test case: Register with duplicate email
def testCase1_register_route():
    payload1 = {
        "username": "Testuser1",
        "email": "Testuser1@example.com",
        "password": "Testpassword1234",
    }
    payload2 = {
        "username": "Testuser2",
        "email": "testuser1@example.com",  # Same email
        "password": "Testpassword1234",
    }

    response = client.post("/auth/register", json=payload1)
    assert response.status_code == 201

    response = client.post("/auth/register", json=payload2)
    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already exists"

# Test case: Register with duplicate username (case insensitive)
def testCase2_register_route():
    payload1 = {
        "username": "Testuser",
        "email": "testuser@example.com",
        "password": "Testpassword1234",
    }
    payload2 = {
        "username": "testuser",  # Same username (case insensitive)
        "email": "testuser2@example.com",
        "password": "Testpassword1234",
    }

    response = client.post("/auth/register", json=payload1)
    assert response.status_code == 201

    response = client.post("/auth/register", json=payload2)
    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already exists"

# Test case: Try Different invalid payloads for registration
def testCase3_register_route():
    payload1 = {
        "username": "Testuser",
        # Missing email and password
    }

    payload2 = {
        "username": "Testuser2",
        "email": "",
        "password": "Testpassword1234",
    }

    payload3 = {
        "username": "Testuser3",
        "email": "testuser3@example.com",
        "password": 1234567,
    }

    payload4 = {
        "username": "Testuser4",
        "email": "testuser4@example.com",
        "password": "Testpassword1234djfasldjflaksdcnasdjfaslf412378ydfhakjdh82345rqwejbr",
    }

    payload5 = {
        "username": "Testuser5",
        "email": "invalid-email-format",
        "password": "Testpassword1234",
    }

    payload6 = {
        "username": "Testuser6😎👌",
        "email": "✅testuser6@example.com",
        "password": "Testpassword1234",
    }

    payload7 = {
        "username": "  Testuser7",
        "email": "    testuser7@example.com    ",
        "password": "Testpassword1234 ",
    }

    payload8 = {
            "username": "Testuser8",
            "email": "testuser8@example.com",
            "password": "Testpassword1234",
            "isadmin": True,
            "isverified": True
        }

    response = client.post("/auth/register", json=payload1)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload2)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload3)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload4)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload5)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload6)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload7)
    assert response.status_code == 422

    response = client.post("/auth/register", json=payload8)
    assert response.status_code == 201
    assert response.json()["message"] == "User registered successfully"
    assert "isadmin" not in response.json() and "isverified" not in response.json()  # Extra fields should not be returned

# ----------------------- Login Route Test Cases -----------------------

# Inject Register user using fixture for login tests
@pytest.fixture()
def InjectRegisterUser():
    payload = {
            "username": "Testuser",
            "email": "testuser@example.com",
            "password": "Testpassword1234",
        }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201

    return response.json()

# Test case: Login with incorrect credentials
def testCase1_login_route(InjectRegisterUser):
    payload = {
        "username": "Testuser",
        "password": "Testpassword123",
    }
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

    payload = {
        "username": "Testuser1234",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

# Test case: Login with leading/trailing spaces in username and password
def testCase2_login_route(InjectRegisterUser):
    payload = {
        "username": "       testuser@example.com",
        "password": "Testpassword1234         ",
    }
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

# Test case: Login with injection attempts in username and password
def testCase3_login_route(InjectRegisterUser):
    payload = {
        "username": "{'$ne': null}",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

# Test case: Login with missing fields in the payload
def testCase4_login_route(InjectRegisterUser):
    payload = {
        "email": "testuser@example.com",
        "password": "Testpassword1234",
    }
    response = client.post("/auth/login", data=payload)
    assert response.status_code == 422

"""
# Test for rate limiting on login and register endpoints

## Token and session

- **Expired token** is rejected
- **Tampered token** (altered payload, invalid signature) is rejected
- **`alg: none` attack** and algorithm confusion
- **Missing, malformed, or wrongly prefixed header** (`Bearer` vs `bearer` vs nothing)
- **Token for a deleted or banned user** is rejected
- **Refresh token flow:** rotation, reuse detection, and expiry
- **Logout:** token or session is actually invalidated
- **Password change:** old tokens are invalidated

## Authorization on protected routes

- **No token, invalid token, expired token** each give 401
- **Valid token but wrong role** gives 403
- **Accessing another user's data** (IDOR)
- **Privilege escalation:** a normal user tries to update their own role

## Password reset and related flows

- **Reset token:** single-use, expires, and is tied to one user
- **Non-existent email:** same response as an existing one
- **Reset link reuse** after the password has been changed
- **Rate limiting** on reset requests

## Security and infrastructure

- **Security headers and cookie flags:** `HttpOnly`, `Secure`, `SameSite`
- **CORS behavior** for allowed and disallowed origins
- **Sensitive data in logs:** passwords and tokens shouldn't appear
- **Error responses** don't leak stack traces or DB errors

## Reliability

- **DB down or timeout:** you get a clean 500/503, not a crash
- **Email service failure** during registration: is the user created or rolled back?
- **Concurrent logins** from multiple devices, if relevant
- **Load and performance:** hashing cost (bcrypt rounds) vs response time under load


"""
