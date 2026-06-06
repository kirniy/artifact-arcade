#!/usr/bin/env python3
"""Print or preview the RP80 photobooth receipt layout."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.hardware.printer.rp80 import create_rp80_printer
from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator


def _default_image() -> Path:
    candidates = [
        Path("/Users/kirniy/dev/modular-arcade/tmp/vnvnc_photobooth_prints/photobooth-20260522_thermal.png"),
        Path("/Users/kirniy/Downloads/IMG_7298.jpeg"),
        Path("/Users/kirniy/Downloads/IMG_7299.jpeg"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("Pass --image; no default test image found")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--preview", type=Path, default=Path("/tmp/rp80_photobooth_receipt.png"))
    parser.add_argument("--no-print", action="store_true")
    args = parser.parse_args()

    image_path = args.image or _default_image()
    generator = PhotoboothRollReceiptGenerator()
    receipt = generator.generate_receipt(
        "photobooth",
        {
            "caricature": str(image_path),
        },
    )
    args.preview.write_bytes(receipt.preview_image)
    print(f"preview: {args.preview}")
    print(f"quote: {receipt.quote}")
    print(f"escpos bytes: {len(receipt.raw_commands)}")

    if args.no_print:
        return

    printer = create_rp80_printer()
    if not await printer.connect():
        raise SystemExit("RP80 printer not connected")
    try:
        ok = await printer.print_raw(receipt.raw_commands)
        print("printed" if ok else "print failed")
    finally:
        await printer.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
