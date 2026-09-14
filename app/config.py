import os
from dotenv import load_dotenv

load_dotenv()

class Settings():
    DB_URL: str = os.getenv("DB_URL","postgresql+asyncpg://myuser:mypassword@localhost:5432/keep_clone_db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

config = Settings()