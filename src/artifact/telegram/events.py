"""Durable event log used by the Telegram admin bot."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterable


DATA_DIR = Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))
EVENT_LOG = Path(os.environ.get("ARCADE_BOT_EVENT_LOG", str(DATA_DIR / "bot_events.jsonl")))


def append_bot_event(event_type: str, payload: dict[str, Any]) -> str:
    """Append one event and return its id."""
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event_id = payload.get("id") or uuid.uuid4().hex
    event = {
        "id": event_id,
        "type": event_type,
        "timestamp": payload.get("timestamp") or time.time(),
        **payload,
    }
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        EVENT_LOG.chmod(0o666)
    except OSError:
        pass
    return event_id


def read_bot_events(path: Path = EVENT_LOG) -> Iterable[dict[str, Any]]:
    """Yield valid events from the JSONL log."""
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event
