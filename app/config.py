import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database URLs (supports standard Railway variable names)
    DATABASE_URL: Optional[str] = None
    DATABASE_PRIVATE_URL: Optional[str] = None
    DATABASE_PUBLIC_URL: Optional[str] = None
    POSTGRES_URL: Optional[str] = None

    @property
    def raw_database_url(self) -> str:
        """Resolve active database URL from environment or fall back to local dev default."""
        url = (
            self.DATABASE_URL
            or self.DATABASE_PRIVATE_URL
            or self.DATABASE_PUBLIC_URL
            or self.POSTGRES_URL
            or os.getenv("DATABASE_URL")
            or os.getenv("DATABASE_PRIVATE_URL")
            or os.getenv("DATABASE_PUBLIC_URL")
            or os.getenv("POSTGRES_URL")
            or "postgresql+asyncpg://postgres:postgres@localhost:5432/bonbons"
        )
        # Strip potential surrounding quotes from Railway dashboard
        return url.strip().strip('"').strip("'")

    @property
    def async_database_url(self) -> str:
        """Ensure the URL uses asyncpg for async SQLAlchemy and fix dialect prefixes."""
        url = self.raw_database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg prefers ssl= over sslmode=
        if "sslmode=" in url:
            url = url.replace("sslmode=", "ssl=")
        return url

    @property
    def sync_database_url(self) -> str:
        """For Alembic migrations requiring a sync driver."""
        url = self.raw_database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @property
    def sanitized_database_url(self) -> str:
        """Safe database URL with password masked for logging."""
        try:
            # Handle custom scheme for urlparse
            temp_url = self.async_database_url.replace("postgresql+asyncpg://", "http://")
            parsed = urlparse(temp_url)
            user = parsed.username or "postgres"
            host = parsed.hostname or "unknown"
            port = f":{parsed.port}" if parsed.port else ""
            db_name = parsed.path or ""
            return f"postgresql+asyncpg://{user}:***@{host}{port}{db_name}"
        except Exception:
            return "postgresql+asyncpg://***"

    @property
    def is_localhost_db(self) -> bool:
        """Detect if the configured database target is pointing to localhost."""
        try:
            temp_url = self.async_database_url.replace("postgresql+asyncpg://", "http://")
            parsed = urlparse(temp_url)
            return parsed.hostname in ("localhost", "127.0.0.1", None)
        except Exception:
            return False

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
