import pytest
from httpx import AsyncClient


def registration_payload(
    username: str = "Testuser",
    email: str = "testuser@example.com",
    password: str = "Testpassword1234",
) -> dict[str, str]:
    return {
        "username": username,
        "email": email,
        "password": password,
    }


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Google Keep Clone API!"}


@pytest.mark.asyncio
async def test_register_route(client: AsyncClient):
    response = await client.post("/auth/register", json=registration_payload())

    assert response.status_code == 201
    assert response.json() == {
        "message": "User registered successfully",
        "username": "Testuser",
        "email": "testuser@example.com",
    }


@pytest.mark.asyncio
async def test_login_route(client: AsyncClient):
    payload = registration_payload()
    register_response = await client.post("/auth/register", json=payload)
    assert register_response.status_code == 201

    response = await client.post(
        "/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_me_route(client: AsyncClient):
    payload = registration_payload()
    await client.post("/auth/register", json=payload)
    login_response = await client.post(
        "/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )

    response = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == payload["username"]
    assert response.json()["email"] == payload["email"]
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient):
    first = registration_payload("Testuser1", "testuser1@example.com")
    second = registration_payload("Testuser2", "TESTUSER1@example.com")

    assert (await client.post("/auth/register", json=first)).status_code == 201
    response = await client.post("/auth/register", json=second)

    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already exists"


@pytest.mark.asyncio
async def test_register_rejects_duplicate_username_case_insensitively(
    client: AsyncClient,
):
    first = registration_payload("Testuser", "testuser@example.com")
    second = registration_payload("testuser", "testuser2@example.com")

    assert (await client.post("/auth/register", json=first)).status_code == 201
    response = await client.post("/auth/register", json=second)

    assert response.status_code == 400
    assert response.json()["detail"] == "Username or email already exists"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"username": "Testuser"},
        {"username": "Testuser2", "email": "", "password": "Testpassword1234"},
        {
            "username": "Testuser3",
            "email": "testuser3@example.com",
            "password": 1234567,
        },
        {
            "username": "Testuser4",
            "email": "testuser4@example.com",
            "password": "Testpassword1234djfasldjflaksdcnasdjfaslf412378ydfhakjdh82345rqwejbr",
        },
        {
            "username": "Testuser5",
            "email": "invalid-email-format",
            "password": "Testpassword1234",
        },
        {
            "username": "Testuser6😎👌",
            "email": "✅testuser6@example.com",
            "password": "Testpassword1234",
        },
        {
            "username": "  Testuser7",
            "email": "    testuser7@example.com    ",
            "password": "Testpassword1234 ",
        },
    ],
)
async def test_register_rejects_invalid_payload(
    client: AsyncClient, payload: dict
):
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_ignores_unknown_fields(client: AsyncClient):
    payload = registration_payload("Testuser8", "testuser8@example.com")
    payload.update({"isadmin": True, "isverified": True})

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert "isadmin" not in response.json()
    assert "isverified" not in response.json()


@pytest.mark.asyncio
async def test_login_rejects_incorrect_credentials(client: AsyncClient):
    payload = registration_payload()
    await client.post("/auth/register", json=payload)

    for login_payload in (
        {"username": "Testuser", "password": "Testpassword123"},
        {"username": "Testuser1234", "password": "Testpassword1234"},
        {
            "username": "       testuser@example.com",
            "password": "Testpassword1234         ",
        },
        {"username": "{'$ne': null}", "password": "Testpassword1234"},
    ):
        response = await client.post("/auth/login", data=login_payload)
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"


@pytest.mark.asyncio
async def test_login_requires_username(client: AsyncClient):
    payload = registration_payload()
    await client.post("/auth/register", json=payload)

    response = await client.post(
        "/auth/login",
        data={"email": payload["email"], "password": payload["password"]},
    )

    assert response.status_code == 422
