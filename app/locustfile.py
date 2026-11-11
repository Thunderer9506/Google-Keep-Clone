import logging
import queue
import sys
from pathlib import Path

from locust import HttpUser, between, events, task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

logger = logging.getLogger("locust_test")

LOCUST_USERNAME_PREFIX = "locust"
LOCUST_EMAIL_DOMAIN = "loadtest.example.com"
LOCUST_PASSWORD = "LocustPassword123"

users = []
user_count = 0


class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        global user_count
        user_count += 1
        self.username = f"{LOCUST_USERNAME_PREFIX}_{user_count:03d}"

        registration_response = self.client.post(
            "/auth/register",
            json={
                "username": self.username,
                "email": f"{self.username}@{LOCUST_EMAIL_DOMAIN}",
                "password": LOCUST_PASSWORD,
            },
            name="POST /auth/register",
        )
        if registration_response.status_code != 201:
            print(
                f"User {self.username} registration failed: "
                f"HTTP {registration_response.status_code} - "
                f"{registration_response.text}"
            )
            return

        response = self.client.post(
            "/auth/login",
            data={
                "username": self.username,
                "password": LOCUST_PASSWORD,
            },
            name="POST /auth/login",
        )

        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                users.append(token)
                self.client.headers.update({"Authorization": f"Bearer {token}"})
                print(f"User {self.username} logged in successfully.")
        else:
            print(
                f"User {self.username} login failed: "
                f"HTTP {response.status_code} - {response.text}"
            )

    def on_stop(self) -> None:
        token = users.pop() if users else None
        if not token:
            print(f"No token found for user {self.username} during logout.")
            return
        response = self.client.delete(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            name="DELETE /auth/logout",
        )
        if response.status_code != 200:
            logger.error(
                "User %s logout failed: HTTP %s - %s",
                self.username,
                response.status_code,
                response.text,
            )
        else:
            print(f"User {self.username} deleted on stop.")

    @task(5)
    def health_check(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(4)
    def list_notes(self) -> None:
        self.client.get("/notes/", name="GET /notes/")

    @task(3)
    def create_note(self) -> None:
        response = self.client.post(
            "/notes/",
            json={
                "title": f"Note by {self.username}",
                "body": "Created during load test.",
                "note_type": "TEXT",
            },
            name="POST /notes/",
        )
        if response.status_code in (200, 201):
            self.note_id = response.json().get("id")

    @task(2)
    def get_note(self) -> None:
        note_id = getattr(self, "note_id", None)
        self.client.get(f"/notes/{note_id}", name="GET /notes/:id")
