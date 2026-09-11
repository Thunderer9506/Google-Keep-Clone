
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy import DateTime
from datetime import datetime
from db import Base

class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    created_at: Mapped[DateTime] = mapped_column(default=datetime.now())