import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.enums import ShellType, FlavorCategory
from app.models.bonbon_image import BonbonImage


class Bonbon(Base):
    __tablename__ = "bonbons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    shell: Mapped[ShellType] = mapped_column(
        SQLEnum(ShellType, name="shell_type", native_enum=False),
        default=ShellType.DARK,
        nullable=False,
    )
    category: Mapped[FlavorCategory] = mapped_column(
        SQLEnum(FlavorCategory, name="flavor_category", native_enum=False),
        default=FlavorCategory.SEASONAL,
        index=True,
        nullable=False,
    )
    allergens: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)

    primary_image_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bonbon_images.id", ondelete="SET NULL", use_alter=True, name="fk_bonbons_primary_image_id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    images: Mapped[List["BonbonImage"]] = relationship(
        "BonbonImage",
        back_populates="bonbon",
        foreign_keys=[BonbonImage.bonbon_id],
        cascade="all, delete-orphan",
        order_by="desc(BonbonImage.created_at)",
    )

    primary_image: Mapped[Optional["BonbonImage"]] = relationship(
        "BonbonImage",
        foreign_keys=[primary_image_id],
        post_update=True,
    )
