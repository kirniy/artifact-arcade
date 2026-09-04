#!/usr/bin/env python3
"""Render deterministic local QA previews for the hidden SPIDERVERSE quest."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from artifact.animation.engine import AnimationEngine
from artifact.core.events import EventBus
from artifact.core.state import StateMachine
from artifact.graphics.renderer import Renderer
from artifact.modes.base import ModeContext
from artifact.modes.spiderverse_quest import QUEST_START_URL, SpiderverseQuestMode
from artifact.printing.spiderverse_quest_roll import (
    SPIDERVERSE_QUEST_MODE_NAME,
    SpiderverseQuestRollReceiptGenerator,
)


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render(output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    context = ModeContext(StateMachine(), EventBus(), Renderer(), AnimationEngine())
    mode = SpiderverseQuestMode(context)
    mode.enter()
    mode.update(740.0)

    main = np.zeros((128, 128, 3), dtype=np.uint8)
    ticker = np.zeros((8, 48, 3), dtype=np.uint8)
    mode.render_main(main)
    mode.render_ticker(ticker)

    main_img = Image.fromarray(main).resize((768, 768), Image.Resampling.NEAREST)
    ticker_img = Image.fromarray(ticker).resize((768, 128), Image.Resampling.NEAREST)
    board = Image.new("RGB", (840, 1040), (8, 10, 16))
    board.paste(main_img, (36, 80))
    board.paste(ticker_img, (36, 890))
    draw = ImageDraw.Draw(board)
    draw.text((36, 22), "SPIDERVERSE QUEST · LOCAL QA", font=_font(28), fill=(245, 235, 213))
    draw.text((36, 860), f"LCD · {mode.get_lcd_text()}", font=_font(22), fill=(235, 28, 48))
    screen_path = output_dir / "spiderverse-quest-ready.png"
    board.save(screen_path)

    phases: list[Image.Image] = []
    for _index in range(4):
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        mode.render_main(frame)
        phases.append(Image.fromarray(frame).resize((384, 384), Image.Resampling.NEAREST))
        mode.update(720.0)
    contact = Image.new("RGB", (768, 768), (8, 10, 16))
    for index, frame in enumerate(phases):
        contact.paste(frame, ((index % 2) * 384, (index // 2) * 384))
    contact_path = output_dir / "spiderverse-quest-idle-contact-sheet.png"
    contact.save(contact_path)

    receipt, _qr_region = SpiderverseQuestRollReceiptGenerator().render_image(
        {"quest_start_url": QUEST_START_URL}
    )
    receipt_path = output_dir / "spiderverse-quest-receipt.png"
    receipt.save(receipt_path)
    return screen_path, contact_path, receipt_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("output/spiderverse/quest"))
    args = parser.parse_args()
    for path in render(args.output_dir):
        print(path.resolve())


if __name__ == "__main__":
    main()
