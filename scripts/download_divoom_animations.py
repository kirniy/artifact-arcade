#!/usr/bin/env python3
"""
Download New Year themed pixel art animations from Divoom gallery.

Usage:
    python scripts/download_divoom_animations.py

Requires: pip install apixoo
"""

import os
import sys
import hashlib
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from apixoo import APIxoo, GalleryCategory, GalleryDimension
except ImportError:
    print("Error: apixoo not installed. Run: pip install apixoo")
    sys.exit(1)


# Divoom credentials
EMAIL = "kirniy@me.com"
PASSWORD = "vocxaz-nYxtuv-birma2"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "divoom_animations"


def md5_hash(password: str) -> str:
    """Create MD5 hash of password as required by Divoom API."""
    return hashlib.md5(password.encode()).hexdigest()


def download_animations():
    """Download New Year/Winter themed animations from Divoom."""

    print("=" * 60)
    print("Divoom Animation Downloader")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    # Login to Divoom
    print(f"\nLogging in as {EMAIL}...")
    api = APIxoo(EMAIL, md5_password=md5_hash(PASSWORD))

    try:
        api.log_in()
        print("Login successful!")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # Try different categories to find New Year/Winter content
    categories_to_try = [
        (GalleryCategory.RECOMMEND, "Recommended"),
        (GalleryCategory.NEW, "New"),
    ]

    downloaded_count = 0

    for category, category_name in categories_to_try:
        print(f"\n--- Fetching {category_name} animations (64x64) ---")

        try:
            # Get 64x64 animations (will scale to 128x128)
            files = api.get_category_files(
                category,
                dimension=GalleryDimension.W64H64,
                page=1,
                per_page=30  # Get first 30
            )

            print(f"Found {len(files)} animations")

            for i, info in enumerate(files):
                try:
                    # Generate filename
                    filename = f"divoom_{category_name.lower()}_{i:03d}_{info.gallery_id}.gif"
                    filepath = OUTPUT_DIR / filename

                    # Skip if already downloaded
                    if filepath.exists():
                        print(f"  [{i+1}] Skipping (exists): {filename}")
                        continue

                    print(f"  [{i+1}] Downloading: {filename}...")

                    # Download and convert to GIF
                    pixel_bean = api.download(info)
                    pixel_bean.save_to_gif(str(filepath), scale=2)  # Scale 2x for 128x128

                    downloaded_count += 1
                    print(f"       Saved: {filepath.name}")

                except Exception as e:
                    print(f"  [{i+1}] Error: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching {category_name}: {e}")
            continue

    print(f"\n{'=' * 60}")
    print(f"Download complete! {downloaded_count} new animations saved.")
    print(f"Location: {OUTPUT_DIR}")
    print(f"{'=' * 60}")

    # List downloaded files
    gif_files = list(OUTPUT_DIR.glob("*.gif"))
    if gif_files:
        print(f"\nTotal GIF files: {len(gif_files)}")
        for f in sorted(gif_files)[:10]:
            print(f"  - {f.name}")
        if len(gif_files) > 10:
            print(f"  ... and {len(gif_files) - 10} more")


if __name__ == "__main__":
    download_animations()
