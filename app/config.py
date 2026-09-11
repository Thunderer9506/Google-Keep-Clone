import os
from dotenv import load_dotenv

load_dotenv()

class Settings():
    DB_URL: str = os.getenv("DB_URL","postgresql://myuser:mypassword@localhost:5432/keep_clone_db")

config = Settings()