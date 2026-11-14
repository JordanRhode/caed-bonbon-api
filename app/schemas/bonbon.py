import re
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import ShellType, FlavorCategory
from app.schemas.image import ImageResponse


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class BonbonBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, example="Salted Caramel")
    description: str = Field("", example="Rich caramel center balanced with a touch of sea salt.")
    shell: ShellType = Field(ShellType.DARK, example=ShellType.DARK)
    category: FlavorCategory = Field(FlavorCategory.SEASONAL, example=FlavorCategory.SEASONAL)
    allergens: List[str] = Field(default_factory=list, example=["Milk", "Soy"])
    is_active: bool = Field(True, description="Whether flavor is currently available/visible")
    sort_order: int = Field(0, description="Order index for display sorting")


class BonbonCreate(BonbonBase):
    slug: Optional[str] = Field(None, max_length=100, example="salted-caramel")

    @field_validator("slug", mode="before")
    @classmethod
    def generate_slug_if_missing(cls, v, info):
        if not v and "name" in info.data:
            return slugify(info.data["name"])
        if v:
            return slugify(v)
        return v


class BonbonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    shell: Optional[ShellType] = None
    category: Optional[FlavorCategory] = None
    allergens: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    primary_image_id: Optional[uuid.UUID] = None

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, v):
        if v is not None:
            return slugify(v)
        return v


class BonbonToggleActive(BaseModel):
    is_active: bool = Field(..., description="Target active status")


class BonbonResponse(BonbonBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    primary_image_id: Optional[uuid.UUID] = None
    primary_image: Optional[ImageResponse] = None
    image_url: Optional[str] = None  # Full URL to processed webp for Next.js flavor showcase
    images: List[ImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
