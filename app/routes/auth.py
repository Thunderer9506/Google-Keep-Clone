from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import bcrypt
import jwt
from config import config
from datetime import datetime, timedelta, timezone

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  

class Credentials(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "Bearer"

SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

users: dict[str, dict] = dict()  # In-memory user store for demonstration purposes

def authenticate_user(username: str, password: str):
    if username in users:
        stored_hashed_password = users[username]["password"]
        bytes_password = password.encode('utf-8')
        if bcrypt.checkpw(bytes_password, stored_hashed_password):
            return True
    return False

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user(token: str = Depends(oauth2_scheme)):
    cred_exc = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise cred_exc
    except Exception:
        raise cred_exc
    user = users[username] if username in users else None
    if user is None:
        raise cred_exc
    return {"username": username, "password": users[username]["password"]}

@auth_router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Placeholder for login logic
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "Bearer"}

@auth_router.post("/register")
async def register(request: Credentials):
    # Placeholder for registration logic
    password = request.password
    bytes_password = password.encode('utf-8')
    hashed_password = bcrypt.hashpw(bytes_password, bcrypt.gensalt())
    users[request.username] = {"password": hashed_password}

    return {"message": "Register endpoint", "username": request.username, "password": password, "hashed_password": hashed_password}