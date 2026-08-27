import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "configure-prize-drum-photobooth.sh"


def _run(
    env_file: Path,
    *args: str,
    secret: str = "s" * 32,
    api_base_url: str = "https://api.vnvnc.ru/",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ARTIFACT_REMOTE_DIR": str(ROOT),
            "ARTIFACT_ENV_FILE": str(env_file),
            "ARTIFACT_KIOSK_DEVICE_ID": "artifact",
            "ARTIFACT_KIOSK_DEVICE_SECRET": secret,
            "VNVNC_KIOSK_API_BASE_URL": api_base_url,
        },
    )


def _values(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def test_configure_prize_drum_stages_signed_production_client_disabled(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("UNRELATED=preserved\nARTIFACT_PRIZE_DRUM_ENABLED=true\n")

    result = _run(env_file, "--disable")

    assert result.returncode == 0
    assert "s" * 32 not in result.stdout + result.stderr
    values = _values(env_file)
    assert values["UNRELATED"] == "preserved"
    assert values["ARTIFACT_PRIZE_DRUM_ENABLED"] == "false"
    assert values["ARTIFACT_KIOSK_STUB"] == "false"
    assert values["ARTIFACT_KIOSK_DEVICE_ID"] == "artifact"
    assert values["ARTIFACT_KIOSK_DEVICE_SECRET"] == "s" * 32
    assert values["VNVNC_KIOSK_API_BASE_URL"] == "https://api.vnvnc.ru"
    assert values["ARTIFACT_MOCK_PRINTER"] == "false"
    assert values["ARTIFACT_MOCK_HARDWARE"] == "false"


def test_configure_prize_drum_enables_only_when_explicit(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    result = _run(env_file, "--enable")
    assert result.returncode == 0
    assert _values(env_file)["ARTIFACT_PRIZE_DRUM_ENABLED"] == "true"


def test_configure_prize_drum_rejects_short_secret(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    result = _run(env_file, "--disable", secret="short")
    assert result.returncode == 2
    assert not env_file.exists()


def test_configure_prize_drum_accepts_literal_tailscale_http(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    result = _run(
        env_file,
        "--disable",
        api_base_url="http://100.114.78.88:8085/",
    )
    assert result.returncode == 0
    assert _values(env_file)["VNVNC_KIOSK_API_BASE_URL"] == "http://100.114.78.88:8085"


@pytest.mark.parametrize(
    "api_base_url",
    (
        "http://api.vnvnc.ru",
        "http://82.38.148.239:8085",
        "http://192.168.2.1:8085",
    ),
)
def test_configure_prize_drum_rejects_non_tailscale_http(
    tmp_path: Path,
    api_base_url: str,
) -> None:
    env_file = tmp_path / ".env"
    result = _run(env_file, "--disable", api_base_url=api_base_url)
    assert result.returncode != 0
    assert not env_file.exists()
