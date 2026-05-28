from pydantic_settings import BaseSettings
from pathlib import Path

# Finds .env relative to this file's location — not relative to
# where you run the command from.
# config.py lives at: backend/app/core/config.py
# .env lives at:      AegisAPI/.env
# parents[0] = core/
# parents[1] = app/
# parents[2] = backend/
# parents[3] = AegisAPI/  ← this is where .env is
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    APP_NAME: str = "AegisAPI"

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()