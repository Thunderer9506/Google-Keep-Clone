from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy import DateTime, String
from datetime import datetime
from db import Base
import uuid

class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now())

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"