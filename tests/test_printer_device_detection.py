import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.hardware.printer import ip802, rp80


def test_regular_file_is_never_detected_as_rp80(monkeypatch, tmp_path) -> None:
    stale = tmp_path / "lp0"
    stale.write_bytes(b"stale print stream")
    monkeypatch.setenv("ARTIFACT_RP80_PRINTER_PORT", str(stale))
    monkeypatch.setenv("ARTIFACT_PRINTER_PORT", str(stale))
    monkeypatch.setattr(rp80.glob, "glob", lambda pattern: [str(stale)])
    monkeypatch.setattr(rp80, "PYUSB_AVAILABLE", False)

    assert rp80.auto_detect_rp80_printer() is None


def test_regular_file_is_never_detected_as_label_printer(monkeypatch, tmp_path) -> None:
    stale = tmp_path / "lp0"
    stale.write_bytes(b"stale print stream")
    monkeypatch.setenv("ARTIFACT_PRINTER_PORT", str(stale))
    monkeypatch.setattr(ip802.glob, "glob", lambda pattern: [str(stale)])
    monkeypatch.setattr(ip802, "PYUSB_AVAILABLE", False)

    assert ip802.auto_detect_label_printer() is None


def test_rp80_file_backend_fails_closed_if_device_disappears(tmp_path) -> None:
    stale = tmp_path / "lp0"
    stale.write_bytes(b"")
    printer = rp80.RP80ReceiptPrinter(port=str(stale))

    assert asyncio.run(printer.connect()) is False
    assert stale.read_bytes() == b""
