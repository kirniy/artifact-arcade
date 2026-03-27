#!/usr/bin/env python3
"""Quick test render for the fiesta theme using the caricature service."""
import asyncio
import os
import sys
from pathlib import Path

# Set up env before imports
os.environ.setdefault("PHOTOBOOTH_THEME", "fiesta")
os.environ.setdefault("ARTIFACT_ENV", "simulator")
os.environ.setdefault("GEMINI_API_KEYS", "AIzaSyBqQs5XGGK9fBCa4mwyOczD2gx9zyySc4U")

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.artifact.ai.caricature import CaricatureService, CaricatureStyle
from PIL import Image
import io

TEST_PHOTO = Path(__file__).parent.parent / "assets" / "images" / "fiesta.png"
OUTPUT_VERTICAL = Path("/tmp/fiesta_test_vertical.jpg")
OUTPUT_SQUARE = Path("/tmp/fiesta_test_square.jpg")


async def main():
    print("Loading test photo...")
    
    # Use fiesta.png as test image since no test_photo.png
    if not TEST_PHOTO.exists():
        print(f"ERROR: test photo not found at {TEST_PHOTO}")
        sys.exit(1)

    with open(TEST_PHOTO, "rb") as f:
        photo_bytes = f.read()

    print(f"Test photo size: {len(photo_bytes)} bytes")
    print("Initializing CaricatureService...")
    
    service = CaricatureService()

    print("Generating FIESTA vertical (9:16)...")
    try:
        result_v = await service.generate_caricature(
            reference_photo=photo_bytes,
            style=CaricatureStyle.PHOTOBOOTH_FIESTA,
        )
        if result_v:
            OUTPUT_VERTICAL.write_bytes(result_v.image_data)
            img = Image.open(io.BytesIO(result_v.image_data))
            print(f"✓ Vertical saved to {OUTPUT_VERTICAL} — size {img.size}")
        else:
            print("✗ Vertical render returned None")
    except Exception as e:
        print(f"✗ Vertical render ERROR: {e}")

    print("Generating FIESTA square (1:1)...")
    try:
        result_s = await service.generate_caricature(
            reference_photo=photo_bytes,
            style=CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE,
        )
        if result_s:
            OUTPUT_SQUARE.write_bytes(result_s.image_data)
            img = Image.open(io.BytesIO(result_s.image_data))
            print(f"✓ Square saved to {OUTPUT_SQUARE} — size {img.size}")
        else:
            print("✗ Square render returned None")
    except Exception as e:
        print(f"✗ Square render ERROR: {e}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
