"""Telegram integration for the VNVNC arcade."""

from __future__ import annotations

from typing import Any


__all__ = ["ArcadeBot", "get_arcade_bot"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from artifact.telegram.bot import ArcadeBot, get_arcade_bot

        return {"ArcadeBot": ArcadeBot, "get_arcade_bot": get_arcade_bot}[name]
    raise AttributeError(name)
