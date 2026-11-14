import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.bonbon import Bonbon
from app.models.bonbon_image import BonbonImage
from app.models.enums import ImageProcessingStatus
from app.schemas.image import ImageResponse
from app.services.image_processor import process_bonbon_image
from app.api.deps import require_auth

router = APIRouter(prefix="/bonbons/{bonbon_id}/images", tags=["Bonbon Images"])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def serialize_image(image: BonbonImage) -> ImageResponse:
    """Format ImageResponse with media URLs."""
    raw_url = f"/media/images/raw/{image.raw_filename}"
    processed_url = (
        f"/media/images/processed/{image.processed_filename}"
        if image.processed_filename
        else None
    )
    return ImageResponse(
        id=image.id,
        bonbon_id=image.bonbon_id,
        raw_filename=image.raw_filename,
        processed_filename=image.processed_filename,
        raw_url=raw_url,
        processed_url=processed_url,
        status=image.status,
        width=image.width,
        height=image.height,
        model_used=image.model_used,
        error_message=image.error_message,
        created_at=image.created_at,
    )


@router.post("", response_model=ImageResponse, dependencies=[Depends(require_auth)])
async def upload_and_process_image(
    bonbon_id: uuid.UUID,
    file: UploadFile = File(..., description="Raw bonbon photo (PNG, JPG, WEBP)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a raw bonbon photo and run it through the background removal
    and touch-up processor (rembg birefnet-general-lite).
    """
    # 1. Ensure bonbon exists
    bonbon = await db.get(Bonbon, bonbon_id)
    if not bonbon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bonbon with ID {bonbon_id} not found.",
        )

    # 2. Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    image_id = uuid.uuid4()
    raw_filename = f"{image_id}{ext}"
    processed_filename = f"{image_id}.webp"

    raw_path = settings.storage_path / "images" / "raw" / raw_filename
    processed_path = settings.storage_path / "images" / "processed" / processed_filename

    # 3. Save raw file to persistent storage
    try:
        content = await file.read()
        raw_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded raw image: {str(e)}",
        )

    # 4. Create image record in database
    image_record = BonbonImage(
        id=image_id,
        bonbon_id=bonbon_id,
        raw_filename=raw_filename,
        processed_filename=processed_filename,
        status=ImageProcessingStatus.PROCESSING,
    )
    db.add(image_record)
    await db.commit()
    await db.refresh(image_record)

    # 5. Process image with rembg pipeline
    try:
        proc_result = await process_bonbon_image(raw_path, processed_path)
        image_record.status = ImageProcessingStatus.COMPLETED
        image_record.width = proc_result["width"]
        image_record.height = proc_result["height"]

        # Automatically promote the newly processed image to primary
        bonbon.primary_image_id = image_record.id
        await db.commit()
        await db.refresh(image_record)
    except Exception as proc_err:
        image_record.status = ImageProcessingStatus.FAILED
        image_record.error_message = str(proc_err)
        await db.commit()
        await db.refresh(image_record)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Image processing failed: {str(proc_err)}",
        )

    return serialize_image(image_record)


@router.get("", response_model=List[ImageResponse], dependencies=[Depends(require_auth)])
async def list_bonbon_images(
    bonbon_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded and processed images for a bonbon."""
    stmt = (
        select(BonbonImage)
        .where(BonbonImage.bonbon_id == bonbon_id)
        .order_by(BonbonImage.created_at.desc())
    )
    result = await db.execute(stmt)
    images = result.scalars().all()
    return [serialize_image(img) for img in images]


@router.post(
    "/{image_id}/set-primary",
    response_model=ImageResponse,
    dependencies=[Depends(require_auth)],
)
async def set_primary_image(
    bonbon_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Set an existing image as the primary display image for this bonbon."""
    bonbon = await db.get(Bonbon, bonbon_id)
    if not bonbon:
        raise HTTPException(status_code=404, detail="Bonbon not found.")

    image = await db.get(BonbonImage, image_id)
    if not image or image.bonbon_id != bonbon_id:
        raise HTTPException(status_code=404, detail="Image not found for this bonbon.")

    bonbon.primary_image_id = image.id
    await db.commit()

    return serialize_image(image)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_auth)],
)
async def delete_image(
    bonbon_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an image and remove its files from persistent volume."""
    image = await db.get(BonbonImage, image_id)
    if not image or image.bonbon_id != bonbon_id:
        raise HTTPException(status_code=404, detail="Image not found for this bonbon.")

    bonbon = await db.get(Bonbon, bonbon_id)
    if bonbon and bonbon.primary_image_id == image.id:
        bonbon.primary_image_id = None

    # Remove files from disk
    raw_path = settings.storage_path / "images" / "raw" / image.raw_filename
    if raw_path.exists():
        raw_path.unlink(missing_ok=True)

    if image.processed_filename:
        proc_path = settings.storage_path / "images" / "processed" / image.processed_filename
        if proc_path.exists():
            proc_path.unlink(missing_ok=True)

    await db.delete(image)
    await db.commit()
