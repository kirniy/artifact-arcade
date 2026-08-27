"""Regression coverage for persistent AI-generation logs."""

from datetime import datetime as RealDatetime

from artifact.ai import logging as ai_logging


class _DayOne(RealDatetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 27, 23, 59, 59, tzinfo=tz)


class _DayTwo(RealDatetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 28, 0, 0, 1, tzinfo=tz)


def test_image_logging_creates_daily_subdirectories_after_midnight(tmp_path, monkeypatch):
    logger = object.__new__(ai_logging.AILogger)
    logger.log_dir = tmp_path

    monkeypatch.setattr(ai_logging, "datetime", _DayOne)
    logger._ensure_directories()
    assert (tmp_path / "2026-08-27" / "images").is_dir()

    monkeypatch.setattr(ai_logging, "datetime", _DayTwo)
    entry_id = logger.log_image_generation(
        category="generated_image",
        image_data=b"png bytes",
        prompt="midnight rollover",
        model="test-model",
    )

    assert entry_id
    day_dir = tmp_path / "2026-08-28"
    assert (day_dir / "images" / f"generated_image_{entry_id}.png").read_bytes() == b"png bytes"
    assert (day_dir / "metadata" / f"generated_image_{entry_id}_meta.json").is_file()
    assert (day_dir / "text").is_dir()
