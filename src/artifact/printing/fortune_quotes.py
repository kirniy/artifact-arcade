"""Fortune quote loading for photobooth receipts."""

from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FORTUNE_PATHS = (
    REPO_ROOT / "data" / "fortunes" / "vnvnc_fortunes.json",
    Path("/Users/kirniy/dev/vnvnc-bot/data/fortunes/vnvnc_fortunes.json"),
    Path("/home/kirniy/vnvnc-bot/data/fortunes/vnvnc_fortunes.json"),
    Path("/home/kirniy/modular-arcade/data/fortunes/vnvnc_fortunes.json"),
)

FALLBACK_QUOTES = [
    "Звезды говорят: сегодня ты выглядишь так, будто у тебя есть план. Не порть легенду.",
    "Судьба намекает: фото получилось опасно хорошо. Покажи тем, кто сомневался.",
    "В ближайшем будущем тебя ждет человек, который скажет: «скинь фотку».",
]

def _clean_quote(text: str) -> str:
    return " ".join(str(text).replace("\n", " ").split()).strip()


def _load_quotes(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: Iterable[object]
    if isinstance(payload, dict):
        records = payload.get("fortunes") or []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    quotes: list[str] = []
    for item in records:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = str(item.get("text") or "")
        else:
            continue

        text = _clean_quote(text)
        if 24 <= len(text) <= 190:
            quotes.append(text)
    return quotes


def pick_fortune_quote(path: str | Path | None = None) -> str:
    """Pick a printable fortune quote from the VNVNC bot corpus."""
    configured = path or os.getenv("ARTIFACT_FORTUNE_QUOTES_PATH")
    corpus_paths = (Path(configured),) if configured else DEFAULT_FORTUNE_PATHS
    for corpus_path in corpus_paths:
        try:
            if not corpus_path.exists():
                continue
            quotes = _load_quotes(corpus_path)
            if quotes:
                return random.choice(quotes)
            logger.warning("No printable fortune quotes found in %s", corpus_path)
        except Exception as exc:
            logger.warning("Failed to load fortune quotes from %s: %s", corpus_path, exc)
    logger.warning("No fortune quote corpus available; using fallback quote")
    return random.choice(FALLBACK_QUOTES)
