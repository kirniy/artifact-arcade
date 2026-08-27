from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canary_units_are_manual_fail_closed_and_restore_production() -> None:
    backend = (ROOT / "scripts/artifact-prize-drum-canary-backend.service").read_text()
    ui = (ROOT / "scripts/artifact-prize-drum-canary-ui.service").read_text()

    assert "\n[Install]\n" not in backend
    assert "\n[Install]\n" not in ui
    assert "EnvironmentFile=/home/kirniy/modular-arcade/.env" in backend
    assert "--host 127.0.0.1 --port 8765" in backend
    assert "BindsTo=artifact-prize-drum-canary-backend.service" in ui
    assert "Conflicts=artifact.service" in ui
    assert "ARTIFACT_PRIZE_DRUM_ENABLED=true" in ui
    assert "ARTIFACT_KIOSK_STUB=false" in ui
    assert "ARTIFACT_MOCK_PRINTER=false" in ui
    assert "VNVNC_KIOSK_API_BASE_URL=http://127.0.0.1:8765" in ui
    assert "ExecStopPost=/bin/systemctl --no-block start artifact.service" in ui
    assert "DEVICE_SECRET=" not in backend + ui


def test_canary_manager_refuses_wrong_printer_and_never_edits_dotenv() -> None:
    script = (ROOT / "scripts/manage-prize-drum-physical-canary.sh").read_text()

    assert "lsusb -d 0fe6:811e" in script
    assert "preflight-prize-drum-deployment.sh\" --hardware-only" in script
    assert "units_are_current" in script
    assert "backend_status" in script and '"401"' in script
    assert "ARTIFACT_KIOSK_DEVICE_SECRET" in script
    assert "systemctl start artifact.service" in script
    assert "configure-prize-drum-photobooth.sh" not in script
    assert "write_text" not in script
    assert "sed -i" not in script
