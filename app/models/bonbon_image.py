import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.enums import ImageProcessingStatus

if TYPE_CHECKING:
    from app.models.bonbon import Bonbon


class BonbonImage(Base):
    __tablename__ = "bonbon_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    bonbon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bonbons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    processed_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[ImageProcessingStatus] = mapped_column(
        SQLEnum(ImageProcessingStatus, name="image_processing_status", native_enum=False),
        default=ImageProcessingStatus.PENDING,
        nullable=False,
    )
    width: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    model_used: Mapped[str] = mapped_column(String(50), default="birefnet-general-lite", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    bonbon: Mapped["Bonbon"] = relationship(
        "Bonbon",
        back_populates="images",
        foreign_keys=[bonbon_id],
    )
