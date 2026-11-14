from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bonbons"

    @property
    def async_database_url(self) -> str:
        """Ensure the URL uses asyncpg for async SQLAlchemy."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """For Alembic migrations requiring a sync driver."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    # Admin Authentication
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_PASSWORD_HASH: Optional[str] = None
    SESSION_LIFETIME_DAYS: int = 30
    COOKIE_NAME: str = "bonbon_session"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Storage
    STORAGE_DIR: str = "./data"

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        (p / "images" / "raw").mkdir(parents=True, exist_ok=True)
        (p / "images" / "processed").mkdir(parents=True, exist_ok=True)
        return p

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Public Read Access toggle
    PUBLIC_READ_ACCESS: bool = False


settings = Settings()
