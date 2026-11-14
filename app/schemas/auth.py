from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(..., description="Single admin password")


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    message: str = "Authenticated successfully"


class VerifyResponse(BaseModel):
    authenticated: bool
    expires_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    message: str
