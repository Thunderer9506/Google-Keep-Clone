from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.routes.auth import get_user
from app.models import User, Tag

from pydantic import BaseModel, Field
from typing import List

tags_router = APIRouter(
    prefix="/tags",
    tags=["tags"]
)

class TagBase(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=50)

class TagResponse(TagBase):
    class Config:
        orm_mode = True

@tags_router.get("/", status_code=status.HTTP_200_OK, response_model=List[TagResponse])
async def get_tags(db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Tag).where(Tag.user_id == user.id)
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@tags_router.post("/", status_code=status.HTTP_201_CREATED, response_model=TagResponse)
async def create_tag(tag: TagBase, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Tag).where(Tag.name == tag.name, Tag.user_id == user.id)
        result = await db.execute(stmt)
        existing_tag = result.scalar_one_or_none()
        if existing_tag:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag already exists")

        new_tag = Tag(name=tag.name, user_id=user.id)
        db.add(new_tag)
        await db.commit()
        await db.refresh(new_tag)
        return new_tag
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@tags_router.patch("/{tag_id}", status_code=status.HTTP_200_OK, response_model=TagResponse)
async def update_tag(tag_id: str, tag: TagBase, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Tag).where(Tag.id == tag_id, Tag.user_id == user.id)
        result = await db.execute(stmt)
        existing_tag = result.scalar_one_or_none()
        if not existing_tag:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

        existing_tag.name = tag.name
        await db.commit()
        await db.refresh(existing_tag)
        return existing_tag
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Tag).where(Tag.id == tag_id, Tag.user_id == user.id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    await db.delete(tag)
    await db.commit()
    return None