import asyncio
from pathlib import Path
from typing import Dict, Any
from PIL import Image, ImageEnhance, ImageFilter
from rembg import remove, new_session

CANVAS_SIZE = 500
SUBJECT_MAX = 400  # Leaves 50px margin on each side
WEBP_QUALITY = 92

_session = None


def get_rembg_session():
    global _session
    if _session is None:
        _session = new_session("birefnet-general-lite")
    return _session


def _process_bonbon_sync(input_path: Path, output_path: Path) -> Dict[str, Any]:
    """
    Synchronous image processing matching caed-nextjs scripts/process_bonbon.py:
    1. Cutout subject background using rembg (birefnet-general-lite)
    2. Crop to bounding box
    3. Scale to max 400px preserving aspect ratio
    4. Contrast enhance (1.08), Color enhance (1.05), UnsharpMask (1.2, 110%, 3)
    5. Center on 500x500 transparent RGBA canvas
    6. Save as WEBP quality 92 method 6
    """
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        cutout = remove(img, session=get_rembg_session())

    bbox = cutout.getbbox()
    if bbox is None:
        raise ValueError(f"rembg produced an empty image for {input_path.name}")
    cropped = cutout.crop(bbox)

    w, h = cropped.size
    scale = SUBJECT_MAX / max(w, h)
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    resized = cropped.resize(new_size, Image.LANCZOS)

    resized = ImageEnhance.Contrast(resized).enhance(1.08)
    resized = ImageEnhance.Color(resized).enhance(1.05)
    resized = resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))

    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    x = (CANVAS_SIZE - new_size[0]) // 2
    y = (CANVAS_SIZE - new_size[1]) // 2
    canvas.paste(resized, (x, y), resized)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "WEBP", quality=WEBP_QUALITY, method=6)

    return {
        "width": CANVAS_SIZE,
        "height": CANVAS_SIZE,
        "file_size": output_path.stat().st_size,
    }


async def process_bonbon_image(input_path: Path, output_path: Path) -> Dict[str, Any]:
    """Asynchronous wrapper that offloads image processing to a worker thread."""
    return await asyncio.to_thread(_process_bonbon_sync, input_path, output_path)
