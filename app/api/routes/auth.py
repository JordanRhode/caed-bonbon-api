from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, VerifyResponse, MessageResponse
from app.services.auth_service import verify_password, create_session, revoke_session, validate_session
from app.api.deps import extract_raw_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with the single admin password and receive a session token."""
    if not verify_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password.",
        )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    token, expires_at = await create_session(
        db=db,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Set HTTP-only secure cookie for browser sessions
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        expires=expires_at,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    return LoginResponse(
        token=token,
        expires_at=expires_at,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    token: str = Depends(extract_raw_token),
    db: AsyncSession = Depends(get_db),
):
    """Log out by invalidating the session and clearing the cookie."""
    if token:
        await revoke_session(db, token)

    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
    )
    return MessageResponse(message="Logged out successfully.")


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    token: str = Depends(extract_raw_token),
    db: AsyncSession = Depends(get_db),
):
    """Verify if the current session token or cookie is valid."""
    if not token:
        return VerifyResponse(authenticated=False)

    session_record = await validate_session(db, token)
    if not session_record:
        return VerifyResponse(authenticated=False)

    return VerifyResponse(
        authenticated=True,
        expires_at=session_record.expires_at,
    )
