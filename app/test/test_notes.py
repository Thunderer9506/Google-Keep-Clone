import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_text_note(client: AsyncClient, auth_user: dict[str, str]):
    payload = {
        "title": "My Text Note",
        "body": "This is the body of the note",
        "color": "#FF5733",
        "note_type": "TEXT",
    }

    response = await client.post("/notes/", json=payload, headers=auth_user)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["body"] == payload["body"]
    assert data["color"] == payload["color"]
    assert data["note_type"] == payload["note_type"]
    assert data["checklist_items"] == []
    assert data["tags"] == []
    assert data["is_archived"] is False
    assert data["is_trashed"] is False
    assert data["is_pinned"] is False
    assert data["id"]


@pytest.mark.asyncio
async def test_create_checklist_note(
    client: AsyncClient, auth_user: dict[str, str]
):
    payload = {
        "title": "Shopping List",
        "body": "Things to buy",
        "note_type": "CHECKLIST",
        "checklist_items": [
            {"content": "Milk", "is_checked": False},
            {"content": "Eggs", "is_checked": True},
        ],
    }

    response = await client.post("/notes/", json=payload, headers=auth_user)

    assert response.status_code == 201
    assert response.json()["note_type"] == "CHECKLIST"
    items = response.json()["checklist_items"]
    assert [item["content"] for item in items] == ["Milk", "Eggs"]
    assert [item["is_checked"] for item in items] == [False, True]


@pytest.mark.asyncio
async def test_create_image_note_requires_image_url(
    client: AsyncClient, auth_user: dict[str, str]
):
    payload = {
        "title": "My Image",
        "body": "A nice picture",
        "note_type": "IMAGE",
    }

    response = await client.post("/notes/", json=payload, headers=auth_user)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_checklist_note_requires_items(
    client: AsyncClient, auth_user: dict[str, str]
):
    payload = {
        "title": "Shopping List",
        "body": "Things to buy",
        "note_type": "CHECKLIST",
    }

    response = await client.post("/notes/", json=payload, headers=auth_user)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_and_get_notes(
    client: AsyncClient, auth_user: dict[str, str]
):
    create_response = await client.post(
        "/notes/",
        json={"title": "Single Note", "body": "Content", "note_type": "TEXT"},
        headers=auth_user,
    )
    note_id = create_response.json()["id"]

    list_response = await client.get("/notes/", headers=auth_user)
    get_response = await client.get(f"/notes/{note_id}", headers=auth_user)

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == note_id
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Single Note"


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient, auth_user: dict[str, str]):
    create_response = await client.post(
        "/notes/",
        json={"title": "Original", "body": "Old body", "note_type": "TEXT"},
        headers=auth_user,
    )
    note_id = create_response.json()["id"]

    response = await client.patch(
        f"/notes/{note_id}",
        json={"title": "Updated Title", "body": "New body", "color": "#00FF00"},
        headers=auth_user,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["body"] == "New body"
    assert response.json()["color"] == "#00FF00"


@pytest.mark.asyncio
async def test_note_state_flags_are_mutually_exclusive(
    client: AsyncClient, auth_user: dict[str, str]
):
    response = await client.post(
        "/notes/",
        json={
            "title": "Archived Note",
            "body": "Content",
            "is_archived": True,
            "is_pinned": True,
        },
        headers=auth_user,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["is_archived"] is True
    assert data["is_pinned"] is False
    assert data["is_trashed"] is False


@pytest.mark.asyncio
async def test_notes_are_isolated_between_users(
    client: AsyncClient, auth_user: dict[str, str]
):
    create_response = await client.post(
        "/notes/",
        json={"title": "Private Note", "body": "Content"},
        headers=auth_user,
    )
    note_id = create_response.json()["id"]

    second_user = {
        "username": "seconduser",
        "email": "seconduser@example.com",
        "password": "Testpassword1234",
    }
    await client.post("/auth/register", json=second_user)
    login_response = await client.post(
        "/auth/login",
        data={
            "username": second_user["username"],
            "password": second_user["password"],
        },
    )
    second_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    response = await client.get(f"/notes/{note_id}", headers=second_headers)

    assert response.status_code == 500
