import logging
from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.routes.auth import get_user
from app.models import User, Tag

from pydantic import BaseModel, ConfigDict, Field
from typing import List

logger = logging.getLogger("google_keep_clone_app.routes.tags")

tags_router = APIRouter(
    prefix="/tags",
    tags=["tags"]
)

class TagBase(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=50)

class TagResponse(TagBase):
    model_config = ConfigDict(from_attributes=True)

@tags_router.get("/", status_code=status.HTTP_200_OK, response_model=List[TagResponse])
async def get_tags(db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Tag).where(Tag.user_id == user.id)
        result = await db.execute(stmt)
        tags = result.scalars().all()
        logger.info("Tags fetched: count=%s user_id=%s", len(tags), user.id)
        return tags
    except Exception:
        logger.exception("Failed to fetch tags: user_id=%s", user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch tags")
    

@tags_router.post("/", status_code=status.HTTP_201_CREATED, response_model=TagResponse)
async def create_tag(tag: TagBase, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    try:
        stmt = select(Tag).where(Tag.name == tag.name, Tag.user_id == user.id)
        result = await db.execute(stmt)
        existing_tag = result.scalar_one_or_none()
        if existing_tag:
            logger.warning("Tag creation rejected because tag already exists: user_id=%s", user.id)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag already exists")

        new_tag = Tag(name=tag.name, user_id=user.id)
        db.add(new_tag)
        await db.commit()
        await db.refresh(new_tag)
        logger.info("Tag created: tag_id=%s user_id=%s", new_tag.id, user.id)
        return new_tag
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to create tag: user_id=%s", user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tag")


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
        logger.info("Tag updated: tag_id=%s user_id=%s", tag_id, user.id)
        return existing_tag
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to update tag: tag_id=%s user_id=%s", tag_id, user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update tag")


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: str, db: AsyncSession = Depends(get_db_session), user: User = Depends(get_user)):
    stmt = select(Tag).where(Tag.id == tag_id, Tag.user_id == user.id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    try:
        await db.delete(tag)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to delete tag: tag_id=%s user_id=%s", tag_id, user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tag")
    logger.info("Tag deleted: tag_id=%s user_id=%s", tag_id, user.id)
    return None