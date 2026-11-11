import logging
import os
import queue
import sys
from pathlib import Path

from locust import HttpUser, between, events, task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

logger = logging.getLogger("locust_test")

SEED_USER_COUNT = 50
SEED_USERNAME_PREFIX = "loadtest"
SEED_EMAIL_DOMAIN = "loadtest.example.com"
SEED_PASSWORD = "LoadtestPassword123"
WAIT_TIME_MIN = "0.05"
WAIT_TIME_MAX = "0.1"

USER_QUEUE = queue.Queue()


@events.test_start.add_listener
def on_test_start(environment, **kwargs) -> None:
    options = getattr(environment, "parsed_options", None)
    runner = environment.runner
    target_users = int(
        getattr(runner, "target_user_count", 0)
        or getattr(options, "users", 0)
        or SEED_USER_COUNT
    )

    while not USER_QUEUE.empty():
        USER_QUEUE.get_nowait()

    for index in range(target_users):
        seeded_user_index = index % SEED_USER_COUNT + 1
        USER_QUEUE.put(f"{SEED_USERNAME_PREFIX}_{seeded_user_index:03d}")


class WebsiteUser(HttpUser):
    wait_time = between(WAIT_TIME_MIN, WAIT_TIME_MAX)

    def on_start(self) -> None:
        self.auth_headers = {}
        self.note_ids: list[str] = []

        try:
            self.username = USER_QUEUE.get_nowait()
        except queue.Empty:
            self.username = f"{SEED_USERNAME_PREFIX}_001"

        response = self.client.post(
            "/auth/login",
            data={
                "username": self.username,
                "password": SEED_PASSWORD,
            },
            name="POST /auth/login",
        )

        if response.status_code != 200:
            logger.error(
                "User %s login failed: HTTP %s - %s",
                self.username,
                response.status_code,
                response.text,
            )
            return

        token = response.json().get("access_token")
        if not token:
            logger.error("User %s login response did not contain a token", self.username)
            return

        self.auth_headers = {"Authorization": f"Bearer {token}"}
        self.client.headers.update(self.auth_headers)

    @task(50)
    def list_notes(self) -> None:
        response = self.client.get("/notes/", name="GET /notes/")
        if response.status_code == 200:
            self.note_ids = [
                note["id"] for note in response.json() if note.get("id")
            ]

    @task(20)
    def get_note(self) -> None:
        if not self.note_ids:
            return
        note_id = self.note_ids[0]
        self.client.get(f"/notes/{note_id}", name="GET /notes/:id")

    @task(15)
    def create_note(self) -> None:
        response = self.client.post(
            "/notes/",
            json={
                "title": f"Load test note by {self.username}",
                "body": "Created during the load test.",
                "note_type": "TEXT",
            },
            name="POST /notes/",
        )
        if response.status_code in (200, 201):
            note_id = response.json().get("id")
            if note_id:
                self.note_ids.append(note_id)

    @task(10)
    def update_note(self) -> None:
        if not self.note_ids:
            return
        note_id = self.note_ids[0]
        self.client.patch(
            f"/notes/{note_id}",
            json={"body": "Updated during the load test."},
            name="PATCH /notes/:id",
        )

    @task(5)
    def list_tags(self) -> None:
        self.client.get("/tags/", name="GET /tags/")
