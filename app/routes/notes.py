from fastapi import APIRouter, Depends, HTTPException, Response, status

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.routes.auth import get_user
from app.models import User, Note, ChecklistItem, Tag, NoteTag
from app.config import config

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List, Literal

notes_router = APIRouter(
    prefix="/notes",
    tags=["notes"]
)

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class ChecklistItemBase(BaseModel):
    content: str
    is_checked: bool = False

# 1. CREATE SCHEMA: Strict requirements for creating a note
class NoteCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=50)
    body: str
    color: str = "#FFFFFF"
    note_type: Literal["TEXT", "CHECKLIST", "IMAGE"] = "TEXT"
    image_url: Optional[str] = None
    checklist_items: Optional[List[ChecklistItemBase]] = None
    is_archived: bool = False
    is_trashed: bool = False
    is_pinned: bool = False
    tags: Optional[List[TagBase]] = None

    @model_validator(mode="after")
    def validate_type_requirements(self):
        if self.note_type == "IMAGE" and not self.image_url:
            raise ValueError("image_url is required for IMAGE notes")
        if self.note_type == "CHECKLIST" and not self.checklist_items:
            raise ValueError("checklist_items is required for CHECKLIST notes")
        return self

# 2. UPDATE SCHEMA: All fields are optional for partial updates (PATCH)
class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=50)
    body: Optional[str] = None
    color: Optional[str] = None
    is_archived: Optional[bool] = None
    is_trashed: Optional[bool] = None
    is_pinned: Optional[bool] = None
    # Lists usually require full replacement on update
    checklist_items: Optional[List[ChecklistItemBase]] = None
    tags: Optional[List[TagBase]] = None

# 3. RESPONSE SCHEMA: What the client actually receives
class NoteResponse(BaseModel):
    id: str
    title: str
    body: str
    color: str
    note_type: str
    image_url: Optional[str]
    is_archived: bool
    is_trashed: bool
    is_pinned: bool
    checklist_items: List[ChecklistItemBase] = []
    tags: List[TagBase] = []
    
    # This config tells Pydantic to read from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)


@notes_router.post("/", status_code=status.HTTP_201_CREATED, response_model=NoteResponse)
async def create_note(note_in: NoteCreate, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        new_note = Note(
            user_id=user.id,
            title=note_in.title,
            body=note_in.body,
            color=note_in.color,
            note_type=note_in.note_type,
            image_url=note_in.image_url,
            is_archived=note_in.is_archived,
            is_trashed=note_in.is_trashed,
            is_pinned=note_in.is_pinned
        )
        
        if note_in.note_type == "CHECKLIST" and note_in.checklist_items:
            new_note.checklist_items = [
                ChecklistItem(content=item.content, is_checked=item.is_checked) 
                for item in note_in.checklist_items
            ]

        if note_in.tags:
            for tag_in in note_in.tags:
                stmt = select(Tag).where(Tag.name == tag_in.name, Tag.user_id == user.id)
                existing_tag = (await db.execute(stmt)).scalar_one_or_none()
                
                tag_obj = existing_tag or Tag(name=tag_in.name, user_id=user.id)
                new_note.tags.append(tag_obj)

        db.add(new_note)
        await db.commit()
        
        await db.refresh(new_note, ["tags", "checklist_items"])
        return new_note

    except Exception as e:
        await db.rollback() # Fix: Await the rollback
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@notes_router.get("/", status_code=status.HTTP_200_OK, response_model=List[NoteResponse])
async def get_notes(
    limit: int = 50, 
    offset: int = 0, 
    db: AsyncSession = Depends(get_db_session), 
    user: User = Depends(get_user)
):
    stmt = (
        select(Note)
        .where(Note.user_id == user.id)
        .options(selectinload(Note.tags), selectinload(Note.checklist_items))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@notes_router.get("/{note_id}", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def get_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
        result = await db.execute(stmt)
        note = result.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        await db.refresh(note, ["tags", "checklist_items"])
        return note
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@notes_router.patch("/{note_id}", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def update_note(note_id: str, note_in: NoteUpdate, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = (
        select(Note)
        .where(Note.id == note_id, Note.user_id == user.id)
        .options(selectinload(Note.tags), selectinload(Note.checklist_items))
    )
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    # Partial update logic: only update fields that were actually provided
    update_data = note_in.model_dump(exclude_unset=True)
    
    # Handle scalar fields dynamically
    for field in ["title", "body", "color", "is_archived", "is_trashed", "is_pinned"]:
        if field in update_data:
            setattr(note, field, update_data[field])

    # Handle relationships manually if they were provided
    if "checklist_items" in update_data and note.note_type == "CHECKLIST":
        # In a real production app, clearing and recreating items drops their primary keys.
        # It is often better to update existing items by ID, but for a Keep clone, full replacement is common.
        note.checklist_items = [
            ChecklistItem(content=item.content, is_checked=item.is_checked) 
            for item in note_in.checklist_items
        ]

    if "tags" in update_data:
        new_tags = []
        for tag_in in note_in.tags:
            tag_stmt = select(Tag).where(Tag.name == tag_in.name, Tag.user_id == user.id)
            existing_tag = (await db.execute(tag_stmt)).scalar_one_or_none()
            new_tags.append(existing_tag or Tag(name=tag_in.name, user_id=user.id))
        note.tags = new_tags

    await db.commit()
    await db.refresh(note, ["tags", "checklist_items"])
    return note


@notes_router.patch("/{note_id}/archive", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def archive_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note.is_archived = True
    await db.commit()
    await db.refresh(note, ["tags", "checklist_items"])
    return note


@notes_router.patch("/{note_id}/pin", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def pin_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note.is_pinned = True
    await db.commit()
    await db.refresh(note, ["tags", "checklist_items"])
    return note


@notes_router.patch("/{note_id}/trash", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def trash_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note.is_trashd = True
    await db.commit()
    await db.refresh(note, ["tags", "checklist_items"])
    return note


@notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    
    await db.delete(note)
    await db.commit()
    return None
