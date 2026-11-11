import argparse
import asyncio
import os
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import delete, select
from dotenv import dotenv_values

parser = argparse.ArgumentParser(description="Manage local load-test data.")
parser.add_argument(
    "--delete",
    action="store_true",
    help="Delete users with the loadtest_ prefix and all related data.",
)
parser.add_argument(
    "--db-url",
    help="SQLAlchemy database URL. Defaults to DB_URL, using localhost for local runs.",
)
args = parser.parse_args()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
database_url = (
    args.db_url
    or os.getenv("DB_URL")
    or dotenv_values(PROJECT_ROOT / ".env").get("DB_URL")
)
if database_url and "@postgres:" in database_url:
    database_url = database_url.replace("@postgres:", "@localhost:")
if database_url:
    os.environ["DB_URL"] = database_url

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db import async_session
from app.models import ChecklistItem, Note, NoteTag, Tag, User

SEED_USER_COUNT = 50
SEED_USERNAME_PREFIX = "loadtest"
SEED_EMAIL_DOMAIN = "loadtest.example.com"
SEED_PASSWORD = "LoadtestPassword123"


async def delete_seeded_data() -> None:
    async with async_session() as session:
        user_ids = select(User.id).where(
            User.username.like(f"{SEED_USERNAME_PREFIX}_%")
        )
        note_ids = select(Note.id).where(Note.user_id.in_(user_ids))
        tag_ids = select(Tag.id).where(Tag.user_id.in_(user_ids))

        await session.execute(
            delete(NoteTag).where(
                NoteTag.note_id.in_(note_ids) | NoteTag.tag_id.in_(tag_ids)
            )
        )
        await session.execute(
            delete(ChecklistItem).where(ChecklistItem.note_id.in_(note_ids))
        )
        await session.execute(delete(Note).where(Note.id.in_(note_ids)))
        await session.execute(delete(Tag).where(Tag.id.in_(tag_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def seed_data() -> None:
    await delete_seeded_data()

    password_hash = bcrypt.hashpw(
        SEED_PASSWORD.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    async with async_session() as session:
        for index in range(1, SEED_USER_COUNT + 1):
            username = f"{SEED_USERNAME_PREFIX}_{index:03d}"
            user = User(
                username=username,
                email=f"{username}@{SEED_EMAIL_DOMAIN}",
                password=password_hash,
            )
            user_tags = [
                Tag(name=f"{username}_work", user=user),
                Tag(name=f"{username}_personal", user=user),
            ]
            user.notes.extend(
                [
                    Note(
                        title=f"{username} project plan",
                        body="Review the project milestones and next steps.",
                        note_type="TEXT",
                        tags=[user_tags[0]],
                    ),
                    Note(
                        title=f"{username} shopping checklist",
                        body="Items to buy this week.",
                        note_type="CHECKLIST",
                        checklist_items=[
                            ChecklistItem(content="Milk", is_checked=False),
                            ChecklistItem(content="Bread", is_checked=True),
                            ChecklistItem(content="Fruit", is_checked=False),
                        ],
                        tags=[user_tags[1]],
                    ),
                    Note(
                        title=f"{username} image reference",
                        body="Reference image for the design task.",
                        note_type="IMAGE",
                        image_url="https://example.com/loadtest-reference.png",
                        tags=user_tags,
                    ),
                ]
            )
            session.add(user)

        await session.commit()


async def main(delete_only: bool) -> None:
    if delete_only:
        await delete_seeded_data()
        print("Seeded users and related data deleted.")
    else:
        await seed_data()
        print(
            f"Created {SEED_USER_COUNT} users with notes, checklist items, and tags."
        )


if __name__ == "__main__":
    asyncio.run(main(args.delete))
