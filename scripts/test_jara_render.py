#!/usr/bin/env python3
"""Generate ЖАРА previews from one or more real booth photos."""

import argparse
import asyncio
import io
import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tmp" / "jara-previews")
    parser.add_argument("--variation-start", type=int, default=0)
    return parser.parse_args()


def jpeg_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        output = io.BytesIO()
        rgb.save(output, format="JPEG", quality=94)
        return output.getvalue()


async def main() -> int:
    args = parse_args()
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    os.environ.setdefault("PHOTOBOOTH_THEME", "jara")
    os.environ.setdefault("ARTIFACT_ENV", "simulator")

    from artifact.ai.caricature import CaricatureService, CaricatureStyle
    from artifact.modes.photobooth import PhotoboothMode, get_moscow_party_stamp
    from artifact.modes.photobooth_themes import THEMES

    args.output_dir.mkdir(parents=True, exist_ok=True)
    service = CaricatureService()
    footer_mode = PhotoboothMode.__new__(PhotoboothMode)
    footer_mode._theme = THEMES["jara"]
    failures = 0
    for index, photo in enumerate(args.photos, start=1):
        result = await service.generate_caricature(
            reference_photo=jpeg_bytes(photo),
            style=CaricatureStyle.PHOTOBOOTH_JARA,
            personality_context=(
                "Do not render footer text. Continue the pool, foam, water, and props full bleed "
                "to the bottom edge; keep faces out of the lowest 13% for the floating info card."
            ),
            extra_reference_images=None,
            prompt_variation_index=args.variation_start + index - 1,
        )
        if not result:
            print(f"FAILED {photo}", file=sys.stderr)
            failures += 1
            continue
        output_index = args.variation_start + index
        output = args.output_dir / f"jara-preview-{output_index:02d}-{photo.stem}.png"
        footer_date, moscow_time = get_moscow_party_stamp(THEMES["jara"])
        branded = footer_mode._stamp_jara_logo(result.image_data)
        output.write_bytes(footer_mode._stamp_jara_footer(branded, footer_date, moscow_time))
        print(output)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
