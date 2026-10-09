from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db_session
from app.routes.auth import get_user
from app.models import User, Note, ChecklistItem, Tag, NoteTag
from app.config import config

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal

notes_router = APIRouter(
    prefix="/notes",
    tags=["notes"]
)

class TagModel(BaseModel):
    name: str = Field(...,
            description="Name of the tag",
            examples=["Work", "Personal", "Important"],
            min_length=1,
            max_length=50)

class ChecklistItemModel(BaseModel):
    content: str = Field(...,
            description="Content of the checklist item",
            examples=["Item 1", "Item 2", "Item 3"])
    is_checked: bool = Field(
            description="Whether the checklist item is checked or not",
            examples=[True, False],
            default=False)

class NotesModel(BaseModel):
    title: str = Field(...,
            description="Title of the note",
            examples=["Meeting Notes", "Shopping List"],
            min_length=3,
            max_length=50)
    body: str = Field(...,
            description="Body of the note",
            examples=["Here are the meeting notes...", "Buy milk, eggs, and bread."]
            )
    color: str = Field(
            description="Color of the note",
            examples=["#FF0000", "#00FF00", "#0000FF"],
            default="#FFFFFF",)
    note_type: Literal["TEXT", "CHECKLIST", "IMAGE"] = Field(
            description="Type of the note",
            examples=["TEXT", "CHECKLIST", "IMAGE"],
            default="TEXT",)
    image_url: Optional[str] = Field(None,
            description="URL of the image for image notes",
            examples=["https://example.com/image.jpg"])
    checklist_items: Optional[List[ChecklistItemModel]] = Field(None,  
            description="List of checklist items for checklist notes",
            examples=[[ChecklistItemModel(content="Item 1", is_checked=False), ChecklistItemModel(content="Item 2", is_checked=True)]])
    is_archived: Optional[bool] = Field(
            description="Whether the note is archived or not",
            
            default=False)
    is_trashed: Optional[bool] = Field(
            description="Whether the note is trashed or not",
            
            default=False)
    is_pinned: Optional[bool] = Field(
            description="Whether the note is pinned or not",
            
            default=False)
    tags: Optional[List[TagModel]] = Field(
            description="List of tags for the note",
            examples=[[TagModel(name="Work"), TagModel(name="Personal")]])

    @model_validator(mode="after")
    def validate_image_url(self):
        if self.note_type == "IMAGE" and not self.image_url:
            raise ValueError("image_url is required for IMAGE notes")
        return self

    @model_validator(mode="after")
    def validate_checklist_items(self):
        if self.note_type == "CHECKLIST" and not self.checklist_items:
            raise ValueError("checklist_items is required for CHECKLIST notes")
        return self


@notes_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_note(notes: NotesModel, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        newNote = Note(
            user_id=user.id,
            title=notes.title,
            body=notes.body,
            color=notes.color,
            note_type=notes.note_type,
            image_url=notes.image_url,
            is_archived=notes.is_archived,
            is_trashed=notes.is_trashed,
            is_pinned=notes.is_pinned
        )
        if notes.note_type == "CHECKLIST" and notes.checklist_items:
            newNote.checklist_items = [ChecklistItem(content=item.content, is_checked=item.is_checked) for item in notes.checklist_items]

        if notes.tags:
            for tag in notes.tags:
                stmt = select(Tag).where(Tag.name == tag.name, Tag.user_id == user.id)
                existing_tag = (await db.execute(stmt)).scalar_one_or_none()
                if existing_tag:
                    newNote.tags.append(existing_tag)
                else:
                    new_tag = Tag(name=tag.name, user_id=user.id)
                    db.add(new_tag)
                    await db.flush()
                    newNote.tags.append(new_tag)
        db.add(newNote)
        await db.flush()
        await db.commit()
        return notes
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))