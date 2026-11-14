"""
Seed script to import existing bonbons and images from caed-nextjs into the PostgreSQL database.

Usage:
    python scripts/seed_from_nextjs.py --nextjs-dir ../caed-nextjs
"""

import argparse
import asyncio
import json
import re
import shutil
import uuid
from pathlib import Path
from sqlalchemy import select
from app.config import settings
from app.database import async_session_factory
from app.models.bonbon import Bonbon
from app.models.bonbon_image import BonbonImage
from app.models.enums import ShellType, FlavorCategory, ImageProcessingStatus


def parse_ts_flavors(flavors_file: Path):
    """Simple parser to extract active signature and seasonal flavors from flavors.ts."""
    if not flavors_file.exists():
        return set(), set()

    content = flavors_file.read_text(encoding="utf-8")
    sig_match = re.search(r"export const SignatureFlavors.*?=\s*\[(.*?)\];", content, re.DOTALL)
    sea_match = re.search(r"export const SeasonalFlavors.*?=\s*\[(.*?)\];", content, re.DOTALL)

    def extract_ids(block: str):
        ids = set()
        if not block:
            return ids
        for line in block.splitlines():
            # Skip commented lines
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            id_match = re.search(r'id:\s*["\']([^"\']+)["\']', line)
            if id_match:
                ids.add(id_match.group(1))
        return ids

    sig_ids = extract_ids(sig_match.group(1)) if sig_match else set()
    sea_ids = extract_ids(sea_match.group(1)) if sea_match else set()
    return sig_ids, sea_ids


async def seed(nextjs_dir: Path):
    bonbons_json_path = nextjs_dir / "src" / "app" / "flavors" / "bonbons.json"
    flavors_ts_path = nextjs_dir / "src" / "app" / "flavors" / "flavors.ts"
    public_bonbons_dir = nextjs_dir / "public" / "bonbons"

    if not bonbons_json_path.exists():
        print(f"Error: {bonbons_json_path} not found.")
        return

    with open(bonbons_json_path, "r", encoding="utf-8") as f:
        bonbons_data = json.load(f)

    sig_ids, sea_ids = parse_ts_flavors(flavors_ts_path)
    active_ids = sig_ids | sea_ids

    storage_processed_dir = settings.storage_path / "images" / "processed"
    storage_raw_dir = settings.storage_path / "images" / "raw"

    count = 0
    async with async_session_factory() as db:
        for slug, item in bonbons_data.items():
            # Check if bonbon already exists
            res = await db.execute(select(Bonbon).where(Bonbon.slug == slug))
            if res.scalar_one_or_none():
                continue

            # Determine category
            if slug in sig_ids:
                category = FlavorCategory.SIGNATURE
            elif slug in sea_ids:
                category = FlavorCategory.SEASONAL
            else:
                category = FlavorCategory.SEASONAL

            # Determine shell
            shell_val = item.get("shell", "dark").lower()
            try:
                shell = ShellType(shell_val)
            except ValueError:
                shell = ShellType.DARK

            is_active = slug in active_ids

            bonbon = Bonbon(
                slug=slug,
                name=item.get("name", slug.replace("-", " ").title()),
                description=item.get("description", ""),
                shell=shell,
                category=category,
                allergens=item.get("allergens", []),
                is_active=is_active,
                sort_order=count,
            )
            db.add(bonbon)
            await db.flush()

            # Check for existing image in public/bonbons/
            # Look for matches like slug.webp, slug.jpg, etc.
            image_candidates = [
                public_bonbons_dir / f"{slug.replace('-', '_')}.webp",
                public_bonbons_dir / f"{slug}.webp",
                public_bonbons_dir / f"{slug.replace('-', '_')}_2.webp",
            ]
            matched_image = None
            for cand in image_candidates:
                if cand.exists():
                    matched_image = cand
                    break

            if matched_image:
                image_id = uuid.uuid4()
                dest_processed = storage_processed_dir / f"{image_id}.webp"
                shutil.copy2(matched_image, dest_processed)

                image_record = BonbonImage(
                    id=image_id,
                    bonbon_id=bonbon.id,
                    raw_filename=f"{image_id}.webp",
                    processed_filename=f"{image_id}.webp",
                    status=ImageProcessingStatus.COMPLETED,
                    width=500,
                    height=500,
                    model_used="existing-asset",
                )
                db.add(image_record)
                await db.flush()
                bonbon.primary_image_id = image_record.id

            count += 1

        await db.commit()
    print(f"Successfully seeded {count} bonbon flavors into database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nextjs-dir", default="../caed-nextjs", help="Path to caed-nextjs directory")
    args = parser.parse_args()
    asyncio.run(seed(Path(args.nextjs_dir).resolve()))
