import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import ImageProcessingStatus


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bonbon_id: uuid.UUID
    raw_filename: str
    processed_filename: Optional[str] = None
    raw_url: str
    processed_url: Optional[str] = None
    status: ImageProcessingStatus
    width: int
    height: int
    model_used: str
    error_message: Optional[str] = None
    created_at: datetime
