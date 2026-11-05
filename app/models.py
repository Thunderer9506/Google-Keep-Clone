from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy import DateTime, String, ForeignKey, Computed, Text, event
from sqlalchemy.dialects.postgresql import TSVECTOR
from datetime import datetime
from app.db import Base
import uuid
from typing import Literal

class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now())

    notes: Mapped[list["Note"]] = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship("Tag", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"

class Note(Base):
    __tablename__ = 'notes'

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    color: Mapped[str] = mapped_column(String, default="#FFFFFF")
    note_type: Mapped[Literal["TEXT", "CHECKLIST", "IMAGE"]] = mapped_column(String, default="TEXT")
    image_url: Mapped[str] = mapped_column(String, nullable=True)

    is_archived: Mapped[bool] = mapped_column(default=False)
    is_trashed: Mapped[bool] = mapped_column(default=False)
    is_pinned: Mapped[bool] = mapped_column(default=False)

    trashed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now())

    search_vector: Mapped[TSVECTOR] = mapped_column(TSVECTOR, Computed("to_tsvector('english', title || ' ' || body)", persisted=True))

    user: Mapped[User] = relationship("User", back_populates="notes")
    checklist_items: Mapped[list["ChecklistItem"]] = relationship("ChecklistItem", back_populates="note", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship("Tag", back_populates="notes", cascade="all", secondary="note_tag")

    def __repr__(self):
        return f"<Note(id={self.id}, title={self.title}, user_id={self.user_id})>"

class ChecklistItem(Base):
    __tablename__ = 'checklist_items'

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(ForeignKey('notes.id'), nullable=False)
    content: Mapped[str] = mapped_column(String)
    is_checked: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now())

    note: Mapped[Note] = relationship("Note", back_populates="checklist_items")

    def __repr__(self):
        return f"<ChecklistItem(id={self.id}, content={self.content}, note_id={self.note_id})>"

class Tag(Base):
    __tablename__ = 'tags'

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now())

    user: Mapped[User] = relationship("User", back_populates="tags")
    notes: Mapped[list["Note"]] = relationship("Note", secondary="note_tag", back_populates="tags")

    def __repr__(self):
        return f"<Tag(id={self.id}, name={self.name})>"

class NoteTag(Base):
    __tablename__ = 'note_tag'

    note_id: Mapped[str] = mapped_column(ForeignKey('notes.id'), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey('tags.id'), primary_key=True)

    def __repr__(self):
        return f"<NoteTag(note_id={self.note_id}, tag_id={self.tag_id})>"