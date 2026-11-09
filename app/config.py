import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("google_keep_clone_app.config")


class Settings():
    DB_URL: str = os.getenv("DB_URL","postgresql+asyncpg://myuser:mypassword@localhost:5432/keep_clone_db")
    TEST_DB_URL: str = os.getenv("TEST_DB_URL","postgresql+asyncpg://myuser:mypassword@localhost:5432/test_db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

config = Settings()
logger.info("Application configuration loaded")