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


def test_rp80_auto_detection_rejects_ip802_usb_node(monkeypatch) -> None:
    path = "/dev/usb/lp0"
    monkeypatch.delenv("ARTIFACT_RP80_PRINTER_PORT", raising=False)
    monkeypatch.setenv("ARTIFACT_PRINTER_PORT", path)
    monkeypatch.setattr(rp80, "_is_character_device", lambda candidate: candidate == path)
    monkeypatch.setattr(rp80.glob, "glob", lambda pattern: [path])
    monkeypatch.setattr(
        rp80,
        "_usb_vid_pid_for_printer_path",
        lambda candidate: (0x353D, 0x1249),
    )
    monkeypatch.setattr(rp80, "PYUSB_AVAILABLE", False)

    assert rp80.auto_detect_rp80_printer() is None


def test_rp80_sysfs_lookup_reads_parent_usb_device_ids(monkeypatch, tmp_path) -> None:
    class_root = tmp_path / "class" / "usb"
    interface = tmp_path / "devices" / "1-2" / "1-2:1.0"
    interface.mkdir(parents=True)
    (interface.parent / "idVendor").write_text("0fe6\n")
    (interface.parent / "idProduct").write_text("811e\n")
    class_node = class_root / "lp0"
    class_node.mkdir(parents=True)
    (class_node / "device").symlink_to(interface)
    monkeypatch.setattr(rp80, "USB_SYSFS_CLASS_ROOTS", (class_root,))

    assert rp80._usb_vid_pid_for_printer_path("/dev/usb/lp0") == (0x0FE6, 0x811E)


def test_rp80_auto_detection_accepts_only_matching_sysfs_ids(monkeypatch) -> None:
    path = "/dev/usb/lp1"
    monkeypatch.delenv("ARTIFACT_RP80_PRINTER_PORT", raising=False)
    monkeypatch.delenv("ARTIFACT_PRINTER_PORT", raising=False)
    monkeypatch.setattr(rp80, "_is_character_device", lambda candidate: candidate == path)
    monkeypatch.setattr(rp80.glob, "glob", lambda pattern: [path])
    monkeypatch.setattr(
        rp80,
        "_usb_vid_pid_for_printer_path",
        lambda candidate: (rp80.USB_VENDOR_ID, rp80.USB_PRODUCT_ID),
    )
    monkeypatch.setattr(rp80, "PYUSB_AVAILABLE", False)

    assert rp80.auto_detect_rp80_printer() == path


def test_explicit_rp80_override_may_trust_live_device_node(monkeypatch) -> None:
    path = "/dev/usb/lp7"
    monkeypatch.setenv("ARTIFACT_RP80_PRINTER_PORT", path)
    monkeypatch.setenv("ARTIFACT_PRINTER_PORT", "/dev/usb/lp0")
    monkeypatch.setattr(rp80, "_is_character_device", lambda candidate: candidate == path)
    monkeypatch.setattr(rp80.glob, "glob", lambda pattern: ["/dev/usb/lp0"])
    monkeypatch.setattr(
        rp80,
        "_usb_vid_pid_for_printer_path",
        lambda candidate: (0x353D, 0x1249),
    )
    monkeypatch.setattr(rp80, "PYUSB_AVAILABLE", False)

    assert rp80.auto_detect_rp80_printer() == path
