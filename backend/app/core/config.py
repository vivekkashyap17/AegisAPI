from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"
KEYS_DIR = Path(__file__).resolve().parent / "keys"


class Settings(BaseSettings):
    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    APP_NAME: str = "AegisAPI"

    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()


def get_private_key() -> str:
    return (KEYS_DIR / "private.pem").read_text()


def get_public_key() -> str:
    return (KEYS_DIR / "public.pem").read_text()