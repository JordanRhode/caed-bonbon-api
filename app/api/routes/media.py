from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from app.config import settings

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/images/processed/{filename}")
async def get_processed_image(filename: str):
    """Serve processed 500x500 bonbon cutout image with public cache headers."""
    # Prevent path traversal
    safe_name = Path(filename).name
    file_path = settings.storage_path / "images" / "processed" / safe_name

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processed image not found.",
        )

    return FileResponse(
        path=file_path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/images/raw/{filename}")
async def get_raw_image(filename: str):
    """Serve raw uploaded bonbon photo."""
    safe_name = Path(filename).name
    file_path = settings.storage_path / "images" / "raw" / safe_name

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw image not found.",
        )

    # Determine media type based on extension
    ext = file_path.suffix.lower()
    media_types = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
    )
