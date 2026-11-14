import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.bonbon import Bonbon
from app.models.bonbon_image import BonbonImage
from app.models.enums import FlavorCategory
from app.schemas.bonbon import (
    BonbonCreate,
    BonbonUpdate,
    BonbonResponse,
    BonbonToggleActive,
)
from app.schemas.image import ImageResponse
from app.api.deps import require_auth, check_read_permission
from app.api.routes.images import serialize_image

router = APIRouter(prefix="/bonbons", tags=["Bonbons"])


def serialize_bonbon(bonbon: Bonbon) -> BonbonResponse:
    """Format BonbonResponse with nested images and primary image URL."""
    serialized_images = [serialize_image(img) for img in (bonbon.images or [])]

    primary_img_resp: Optional[ImageResponse] = None
    image_url: Optional[str] = None

    if bonbon.primary_image:
        primary_img_resp = serialize_image(bonbon.primary_image)
        image_url = primary_img_resp.processed_url
    elif serialized_images:
        # Fallback to newest completed image if primary_image_id wasn't set
        for img in serialized_images:
            if img.processed_url:
                primary_img_resp = img
                image_url = img.processed_url
                break

    return BonbonResponse(
        id=bonbon.id,
        slug=bonbon.slug,
        name=bonbon.name,
        description=bonbon.description,
        shell=bonbon.shell,
        category=bonbon.category,
        allergens=bonbon.allergens or [],
        is_active=bonbon.is_active,
        sort_order=bonbon.sort_order,
        primary_image_id=bonbon.primary_image_id,
        primary_image=primary_img_resp,
        image_url=image_url,
        images=serialized_images,
        created_at=bonbon.created_at,
        updated_at=bonbon.updated_at,
    )


@router.get("", response_model=List[BonbonResponse])
async def list_bonbons(
    active_only: bool = Query(False, description="Filter for only active flavors"),
    category: Optional[FlavorCategory] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
    _auth=Depends(check_read_permission),
):
    """
    List bonbon flavors with optional filters for active status and category.
    By default requires an authenticated session unless PUBLIC_READ_ACCESS=true.
    """
    stmt = (
        select(Bonbon)
        .options(
            selectinload(Bonbon.images),
            selectinload(Bonbon.primary_image),
        )
        .order_by(Bonbon.sort_order.asc(), Bonbon.name.asc())
    )

    if active_only:
        stmt = stmt.where(Bonbon.is_active.is_(True))

    if category:
        stmt = stmt.where(Bonbon.category == category)

    result = await db.execute(stmt)
    bonbons = result.scalars().all()
    return [serialize_bonbon(b) for b in bonbons]


@router.get("/{id_or_slug}", response_model=BonbonResponse)
async def get_bonbon(
    id_or_slug: str,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(check_read_permission),
):
    """Retrieve a single bonbon flavor by UUID or slug."""
    stmt = select(Bonbon).options(
        selectinload(Bonbon.images),
        selectinload(Bonbon.primary_image),
    )

    try:
        val_uuid = uuid.UUID(id_or_slug)
        stmt = stmt.where(Bonbon.id == val_uuid)
    except ValueError:
        stmt = stmt.where(Bonbon.slug == id_or_slug)

    result = await db.execute(stmt)
    bonbon = result.scalar_one_or_none()

    if not bonbon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bonbon '{id_or_slug}' not found.",
        )

    return serialize_bonbon(bonbon)


@router.post("", response_model=BonbonResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
async def create_bonbon(
    payload: BonbonCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new bonbon flavor."""
    # Check for existing slug
    stmt = select(Bonbon).where(Bonbon.slug == payload.slug)
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A bonbon with slug '{payload.slug}' already exists.",
        )

    bonbon = Bonbon(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        shell=payload.shell,
        category=payload.category,
        allergens=payload.allergens,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(bonbon)
    await db.commit()

    # Re-fetch with relationships loaded
    return await get_bonbon(str(bonbon.id), db=db)


@router.patch("/{bonbon_id}", response_model=BonbonResponse, dependencies=[Depends(require_auth)])
async def update_bonbon(
    bonbon_id: uuid.UUID,
    payload: BonbonUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update fields of an existing bonbon flavor."""
    bonbon = await db.get(Bonbon, bonbon_id)
    if not bonbon:
        raise HTTPException(status_code=404, detail="Bonbon not found.")

    update_data = payload.model_dump(exclude_unset=True)

    if "slug" in update_data and update_data["slug"] != bonbon.slug:
        # Check slug conflict
        existing = await db.execute(select(Bonbon).where(Bonbon.slug == update_data["slug"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Slug '{update_data['slug']}' is already in use.",
            )

    for field, val in update_data.items():
        setattr(bonbon, field, val)

    await db.commit()
    return await get_bonbon(str(bonbon.id), db=db)


@router.patch("/{bonbon_id}/activate", response_model=BonbonResponse, dependencies=[Depends(require_auth)])
async def toggle_bonbon_active(
    bonbon_id: uuid.UUID,
    payload: BonbonToggleActive,
    db: AsyncSession = Depends(get_db),
):
    """Convenience endpoint to quickly activate or deactivate a bonbon flavor."""
    bonbon = await db.get(Bonbon, bonbon_id)
    if not bonbon:
        raise HTTPException(status_code=404, detail="Bonbon not found.")

    bonbon.is_active = payload.is_active
    await db.commit()
    return await get_bonbon(str(bonbon.id), db=db)


@router.delete("/{bonbon_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)])
async def delete_bonbon(
    bonbon_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a bonbon flavor and all associated images from the volume and database."""
    stmt = (
        select(Bonbon)
        .options(selectinload(Bonbon.images))
        .where(Bonbon.id == bonbon_id)
    )
    result = await db.execute(stmt)
    bonbon = result.scalar_one_or_none()

    if not bonbon:
        raise HTTPException(status_code=404, detail="Bonbon not found.")

    # Remove files from persistent disk
    for image in bonbon.images:
        raw_path = settings.storage_path / "images" / "raw" / image.raw_filename
        raw_path.unlink(missing_ok=True)
        if image.processed_filename:
            proc_path = settings.storage_path / "images" / "processed" / image.processed_filename
            proc_path.unlink(missing_ok=True)

    await db.delete(bonbon)
    await db.commit()
