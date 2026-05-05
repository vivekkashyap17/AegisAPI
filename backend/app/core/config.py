from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/aegisapi"
    SYNC_DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/aegisapi"
    APP_NAME: str = "Adaptive API Security Mesh"

    class Config:
        env_file = ".env"

settings = Settings()