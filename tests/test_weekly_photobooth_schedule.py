import io
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.photobooth import PhotoboothMode, get_moscow_party_stamp
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE = ROOT / "scripts" / "sync-weekly-photobooth-theme.sh"
MOSCOW = timezone(timedelta(hours=3))


def scheduled_theme(at: str, tmp_path: Path) -> str:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED=1\n"
        "PHOTOBOOTH_THEME=manual-test\n"
        "PHOTOBOOTH_MENU_MODES=manual_test\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(SCHEDULE), "--dry-run", "--at", at],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ARTIFACT_REMOTE_DIR": str(ROOT),
            "ARTIFACT_ENV_FILE": str(env_file),
        },
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return values["THEME_TARGET"]


def test_weekly_theme_schedule_boundaries(tmp_path: Path) -> None:
    assert scheduled_theme("4:2259", tmp_path) == "vse-svoi"
    assert scheduled_theme("4:2300", tmp_path) == "2k17"
    assert scheduled_theme("5:1200", tmp_path) == "2k17"
    assert scheduled_theme("6:2359", tmp_path) == "2k17"
    assert scheduled_theme("7:0659", tmp_path) == "2k17"
    assert scheduled_theme("7:0700", tmp_path) == "vse-svoi"
    assert scheduled_theme("1:1200", tmp_path) == "vse-svoi"


def test_2k17_footer_uses_live_time_and_club_night_date() -> None:
    theme = THEMES["2k17"]
    assert get_moscow_party_stamp(
        theme, datetime(2026, 8, 15, 2, 17, tzinfo=MOSCOW)
    ) == ("14.08.2017", "02:17")

    source = io.BytesIO()
    Image.new("RGB", (900, 1600), "#7755aa").save(source, format="PNG")
    mode = PhotoboothMode.__new__(PhotoboothMode)
    stamped = mode._stamp_2k17_footer(source.getvalue(), "14.08.2017", "02:17")
    rendered = Image.open(io.BytesIO(stamped))
    assert rendered.size == (900, 1600)
    assert rendered.getpixel((10, 1590)) == (255, 255, 255)


def test_2k17_activation_keeps_current_ai_stack() -> None:
    script = (ROOT / "scripts" / "activate-2k17-photobooth.sh").read_text()
    assert "set_env PHOTOBOOTH_THEME 2k17" in script
    assert "set_env PHOTOBOOTH_MENU_MODES 2k17" in script
    assert "set_env PHOTOBOOTH_AI_ENABLED true" in script
    assert "set_env ARTIFACT_IMAGE_PROVIDER vertex" in script
    assert "set_env GEMINI_IMAGE_MODEL gemini-3.1-flash-lite-image" in script
