import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy import delete, select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.db import get_db_session
from app.models import ChecklistItem, Note, NoteTag, Tag, User
from app.config import config

from pydantic import BaseModel, Field, field_validator
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("google_keep_clone_app.routes.auth")


SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class Credentials(BaseModel):
    username: str = Field(
        ...,
        description="The username of the user",
        examples=["JohnDoe"],
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
    )
    email: str = Field(
        ...,
        description="The email of the user",
        examples=["john.doe@example.com"],
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    password: str = Field(
        ...,
        description="The user's password",
        examples=["Password123"],
        min_length=6,
        max_length=50,
        pattern=r"^[a-zA-Z\d@$!%*?&]{6,50}$",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain a lowercase letter")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain an uppercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain a digit")
        return value

class Token(BaseModel):
    access_token: str
    token_type: str = "Bearer"

async def authenticate_user(username: str, password: str, session: AsyncSession) -> User | None:
    try:
        findUser_stmt = select(User).where(or_(User.username == username, User.email == username))
        user = await session.execute(findUser_stmt)
        user: User | None = user.scalar_one_or_none()

        if user is None:
            return None

        if bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
            logger.info("Authenticated user: user_id=%s", user.id)
            return user
    except Exception as e:
        logger.exception("Unexpected error while authenticating user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while authenticating the user",
        )

    return None

def create_access_token(payload: dict)-> str:
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    to_encode.update({"iat": now})
    encoded_jwt = jwt.encode(payload = to_encode, key = SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user(token: str = Depends(oauth2_scheme), db_session: AsyncSession = Depends(get_db_session)) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        userId: str = payload.get("sub")
        if userId is None:
            raise cred_exc
    except jwt.PyJWTError:
        logger.warning("Rejected invalid authentication token")
        raise cred_exc

    try:
        findUser_stmt = select(User).where(User.id == userId)
        user = await db_session.execute(findUser_stmt)
        user: User | None = user.scalar_one_or_none()
        if user is None:
            raise cred_exc
    except SQLAlchemyError:
        logger.exception("Database error while loading authenticated user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )

    return user

@auth_router.post("/login", response_model=Token, description="Generate token", summary="Login User", status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_db_session)):
    user = await authenticate_user(form_data.username, form_data.password, session=session)
    if not user:
        logger.warning("Login rejected for username=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = {"sub": user.id, "username": user.username, "email": user.email}
    access_token = create_access_token(payload)
    logger.info("User logged in successfully: user_id=%s", user.id)
    return Token(access_token=access_token, token_type="Bearer")

@auth_router.delete("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: User = Depends(get_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        note_ids = select(Note.id).where(Note.user_id == current_user.id)
        tag_ids = select(Tag.id).where(Tag.user_id == current_user.id)

        await db_session.execute(
            delete(NoteTag).where(
                NoteTag.note_id.in_(note_ids) | NoteTag.tag_id.in_(tag_ids)
            )
        )
        await db_session.execute(
            delete(ChecklistItem).where(ChecklistItem.note_id.in_(note_ids))
        )
        await db_session.execute(delete(Note).where(Note.id.in_(note_ids)))
        await db_session.execute(delete(Tag).where(Tag.id.in_(tag_ids)))
        await db_session.execute(delete(User).where(User.id == current_user.id))
        await db_session.commit()
    except SQLAlchemyError:
        await db_session.rollback()
        logger.exception("User logout cleanup failed due to a database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )

    logger.info("User logged out and deleted successfully: user_id=%s", current_user.id)
    return {"message": "User logged out and deleted successfully"}

async def check_before_register(user: User, db_session: AsyncSession):
    try:
        findUser_stmt = select(User).where(
            or_(func.lower(User.username) == user.username.lower(),
                func.lower(User.email) == user.email.lower())
        )
        existing_user = await db_session.execute(findUser_stmt)
        existing_user: User | None = existing_user.scalar_one_or_none()
        if existing_user is not None:
            logger.warning("Registration rejected because username or email already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists",
            )
    except SQLAlchemyError:
        logger.exception("Database error while checking user registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )

@auth_router.post("/register", description="Register a new user", summary="User Registration", status_code=status.HTTP_201_CREATED)
async def register(req: Credentials, db_session: AsyncSession = Depends(get_db_session)):
    try:
        password = req.password
        bytes_password = password.encode('utf-8')
        hashed_password = bcrypt.hashpw(bytes_password, bcrypt.gensalt())
        newUser = User(
            username=req.username,
            email=req.email,
            password=hashed_password.decode("utf-8")
        )
        await check_before_register(newUser, db_session)
        db_session.add(newUser)
        await db_session.commit()
        logger.info("User registered successfully: username=%s", req.username)
    except IntegrityError:
        await db_session.rollback()
        logger.exception("User registration failed due to a database integrity error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )
    except SQLAlchemyError:
        await db_session.rollback()
        logger.exception("User registration failed due to a database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )
    return {"message": "User registered successfully"}