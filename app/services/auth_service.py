import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import bcrypt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.session import Session


def hash_password(password: str) -> str:
    """Generate a bcrypt hash of a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str) -> bool:
    """Verify single admin password against ADMIN_PASSWORD_HASH or ADMIN_PASSWORD."""
    if settings.ADMIN_PASSWORD_HASH:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                settings.ADMIN_PASSWORD_HASH.encode("utf-8"),
            )
        except Exception:
            return False

    if settings.ADMIN_PASSWORD:
        return secrets.compare_digest(plain_password, settings.ADMIN_PASSWORD)

    # If neither is set, fail-safe block all access
    return False


def hash_session_token(token: str) -> str:
    """Hash raw session token for database lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, datetime]:
    """Generate a new secure session token, persist its hash, and return raw token."""
    raw_token = secrets.token_hex(32)
    token_hash = hash_session_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_LIFETIME_DAYS)

    session_record = Session(
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session_record)
    await db.commit()

    return raw_token, expires_at


async def validate_session(
    db: AsyncSession,
    raw_token: str,
) -> Optional[Session]:
    """Validate raw token against the sessions table and update last_used_at."""
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)

    stmt = select(Session).where(
        Session.token_hash == token_hash,
        Session.expires_at > now,
    )
    result = await db.execute(stmt)
    session_record = result.scalar_one_or_none()

    if session_record:
        session_record.last_used_at = now
        await db.commit()

    return session_record


async def revoke_session(
    db: AsyncSession,
    raw_token: str,
) -> bool:
    """Revoke/delete an active session."""
    token_hash = hash_session_token(raw_token)
    stmt = delete(Session).where(Session.token_hash == token_hash)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0
