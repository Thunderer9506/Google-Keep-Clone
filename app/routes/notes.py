from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.routes.auth import get_user
from app.models import User, Note, ChecklistItem, Tag

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

class TagResponse(TagBase):
    id: str
    
class ChecklistItemResponse(ChecklistItemBase):
    id: str

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=50)
    body: str
    color: str = "#FFFFFF"
    note_type: Literal["TEXT", "CHECKLIST", "IMAGE"] = "TEXT"
    image_url: Optional[str] = None
    is_archived: Optional[bool] = False
    is_trashed: Optional[bool] = False
    is_pinned: Optional[bool] = False
    checklist_items: Optional[List[ChecklistItemBase]] = []
    tags: Optional[List[TagBase]] = []

    @model_validator(mode="after")
    def validate_type_requirements(self):
        if self.note_type == "IMAGE" and not self.image_url:
            raise ValueError("image_url is required for IMAGE notes")
        if self.note_type == "CHECKLIST" and not self.checklist_items:
            raise ValueError("checklist_items is required for CHECKLIST notes")
        return self

    @model_validator(mode="after")
    def enforce_mutual_exclusivity(self):
        if self.is_trashed is True:
            self.is_pinned = False
            self.is_archived = False
        elif self.is_archived is True:
            self.is_pinned = False
            self.is_trashed = False
        elif self.is_pinned is True:
            self.is_archived = False
            self.is_trashed = False
            
        return self

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=50)
    body: Optional[str] = None
    color: Optional[str] = None
    image_url: Optional[str] = None
    is_archived: Optional[bool] = None
    is_trashed: Optional[bool] = None
    is_pinned: Optional[bool] = None
    checklist_items: Optional[List[ChecklistItemBase]] = []
    tags: Optional[List[TagBase]] = []

    @model_validator(mode="after")
    def enforce_mutual_exclusivity(self):
        if self.is_trashed is True:
            self.is_pinned = False
            self.is_archived = False
        elif self.is_archived is True:
            self.is_pinned = False
            self.is_trashed = False
        elif self.is_pinned is True:
            self.is_archived = False
            self.is_trashed = False
            
        return self

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
    checklist_items: List[ChecklistItemResponse] = []
    tags: List[TagResponse] = []

    model_config = ConfigDict(from_attributes=True)


@notes_router.get("/", status_code=status.HTTP_200_OK, response_model=List[NoteResponse])
async def get_notes(
    limit: int = 50,
    offset: int = 0,
    archived: Optional[bool] = None,
    trashed: Optional[bool] = None,
    pinned: Optional[bool] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_user)
):
    try:
        stmt = (
            select(Note)
            .where(Note.user_id == user.id)
            .options(selectinload(Note.tags), selectinload(Note.checklist_items))
            .limit(limit)
            .offset(offset)
        )
        if archived is not None:
            stmt = stmt.where(Note.is_archived == archived)
        if trashed is not None:
            stmt = stmt.where(Note.is_trashed == trashed)
        if pinned is not None:
            stmt = stmt.where(Note.is_pinned == pinned)
        if tag:
            stmt = stmt.join(Note.tags).where(Tag.id == tag)
        if search:
            stmt = stmt.where(Note.search_vector.contains(search))

        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch notes")


@notes_router.get("/{note_id}", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def get_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = (
            select(Note)
            .where(Note.id == note_id, Note.user_id == user.id)
            .options(selectinload(Note.tags), selectinload(Note.checklist_items))
        )
        result = await db.execute(stmt)
        note = result.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return note
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch note")


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

        if note_in.checklist_items != []:
            for item in note_in.checklist_items:
                new_note.checklist_items.append(ChecklistItem(
                    content=item.content,
                    is_checked=item.is_checked
                ))

        if note_in.tags != []:
            for tag_data in note_in.tags:
                stmt = select(Tag).where(Tag.name == tag_data.name, Tag.user_id == user.id)
                result = await db.execute(stmt)
                existing_tag = result.scalar_one_or_none()
                if existing_tag:
                    new_note.tags.append(existing_tag)
                else:
                    new_tag = Tag(name=tag_data.name, user_id=user.id)
                    db.add(new_tag)
                    new_note.tags.append(new_tag)

        db.add(new_note)
        await db.commit()
        await db.refresh(new_note, ["tags", "checklist_items"])
        return new_note

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create note")


@notes_router.patch("/{note_id}", status_code=status.HTTP_200_OK, response_model=NoteResponse)
async def update_note(note_id: str, note_in: NoteUpdate, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = (select(Note)
                .where(Note.id == note_id, Note.user_id == user.id)
                .options(selectinload(Note.tags), selectinload(Note.checklist_items))
                )
        result = await db.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

        update_data = note_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "checklist_items":
                note.checklist_items.clear()
                for item in value:
                    note.checklist_items.append(ChecklistItem(
                        content=item.content,
                        is_checked=item.is_checked
                    ))
            elif field == "tags":
                note.tags.clear()
                for tag_data in value:
                    stmt = select(Tag).where(Tag.id == tag_data.id, Tag.user_id == user.id)
                    result = await db.execute(stmt)
                    existing_tag = result.scalar_one_or_none()
                    if existing_tag:
                        note.tags.append(existing_tag)
                    else:
                        new_tag = Tag(name=tag_data.name, user_id=user.id)
                        db.add(new_tag)
                        note.tags.append(new_tag)
            else:
                setattr(note, field, value)

        await db.commit()
        await db.refresh(note, ["tags", "checklist_items"])
        return note
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch note")


@notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Note).where(Note.id == note_id, Note.user_id == user.id)
        result = await db.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

        if note.is_archived or note.is_pinned:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete archived or pinned notes")

        if not note.is_trashed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note must be trashed before deletion")

        await db.delete(note)
        await db.commit()
        return None
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete note")

