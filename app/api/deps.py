from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.session import Session
from app.services.auth_service import validate_session

bearer_scheme = HTTPBearer(auto_error=False)


def extract_raw_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """Extract session token from Bearer header or HTTP-only cookie."""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials

    # Fall back to cookie
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    if cookie_token:
        return cookie_token

    return None


async def require_auth(
    token: Optional[str] = Depends(extract_raw_token),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Dependency that enforces a valid authenticated session."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_record = await validate_session(db, token)
    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session_record


async def check_read_permission(
    request: Request,
    token: Optional[str] = Depends(extract_raw_token),
    db: AsyncSession = Depends(get_db),
) -> Optional[Session]:
    """
    Allow public GET access only if PUBLIC_READ_ACCESS is explicitly enabled.
    Otherwise, require authentication.
    """
    if settings.PUBLIC_READ_ACCESS:
        if token:
            return await validate_session(db, token)
        return None

    # Strict mode: auth is required even for reads
    return await require_auth(token=token, db=db)
