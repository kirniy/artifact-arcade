import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from artifact.utils import s3_upload as upload


@pytest.fixture
def spool(monkeypatch, tmp_path):
    monkeypatch.setattr(upload, "UPLOAD_SPOOL_DIR", tmp_path)
    monkeypatch.setattr(upload, "_load_selectel_credentials", lambda: {"configured": True})
    monkeypatch.setattr(upload, "generate_qr_image", lambda url: None)
    return tmp_path


@pytest.mark.parametrize("failure", ["rejected", "timeout", "missing_cli"])
def test_failed_upload_stays_queued_without_claiming_success(monkeypatch, spool, failure):
    def fail(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("aws", 180)
        if failure == "missing_cli":
            raise FileNotFoundError("aws")
        return subprocess.CompletedProcess([], 1, b"", b"network unavailable")

    monkeypatch.setattr(upload, "_upload_local_path_to_s3", fail)
    info = upload.pre_generate_upload_info("photobooth", "png")
    result = upload.upload_bytes_to_s3(b"saved photo", "photobooth", "png", "image/png", info)
    assert not result.success
    assert result.queued
    assert result.short_url == info.short_url
    assert (spool / "photobooth" / info.filename).read_bytes() == b"saved photo"
    assert (spool / "photobooth" / f"{info.filename}.json").exists()


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("aws", 180), FileNotFoundError("aws")])
def test_cli_exception_uses_direct_upload(monkeypatch, tmp_path, error):
    monkeypatch.setattr(upload, "AWS_CLI_AVAILABLE", True)
    monkeypatch.setattr(upload, "AWS_CLI_PATH", "aws")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(upload, "_run_aws_command", fail)
    calls = []
    def direct(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess([], 0, b"", b"")
    monkeypatch.setattr(upload, "_upload_local_path_to_s3_direct", direct)
    result = upload._upload_local_path_to_s3("photo.png", "artifact/photobooth/photo.png", "image/png")
    assert result.returncode == 0
    assert calls[0][0] == ("photo.png", "artifact/photobooth/photo.png", "image/png")


def test_missing_spool_payload_is_not_reported_as_queued(monkeypatch, spool):
    def lose_payload(path, *args, **kwargs):
        Path(path).unlink()
        raise FileNotFoundError(path)
    monkeypatch.setattr(upload, "_upload_local_path_to_s3", lose_payload)
    info = upload.pre_generate_upload_info("photobooth", "png")
    result = upload.upload_bytes_to_s3(b"photo", "photobooth", pre_info=info)
    assert not result.success
    assert not result.queued


def test_photobooth_pending_event_keeps_qr_but_does_not_announce_ready(monkeypatch):
    from artifact.modes import photobooth
    from artifact.telegram.bot import ArcadeBot

    mode = object.__new__(photobooth.PhotoboothMode)
    mode._state = photobooth.PhotoboothState(is_uploading=True)
    mode._theme = SimpleNamespace(id="vse-svoi", event_name="ВСЕ СВОИ")
    events = []
    monkeypatch.setattr(photobooth, "append_bot_event", lambda kind, event: events.append(event))
    result = upload.UploadResult(success=False, queued=True, short_url="https://vnvnc.ru/p/example")
    mode._on_upload_complete(result)
    assert mode._state.qr_url == result.short_url
    assert not mode._state.is_uploading
    assert events[0]["queued"] and not events[0]["success"]
    assert "Новое фото готово" not in ArcadeBot._photo_caption(events[0])
    assert "загрузка ожидает повтора" in ArcadeBot._photo_caption(events[0])


def test_spool_retry_announces_success_only_after_upload(monkeypatch, spool):
    from artifact.telegram import events

    info = upload.pre_generate_upload_info("photobooth", "png")
    pending = upload._create_pending_upload(
        b"saved photo", prefix="photobooth", filename=info.filename,
        extension="png", content_type="image/png", s3_key=info.s3_key, short_id=info.short_id,
    )
    emitted = []
    monkeypatch.setattr(events, "append_bot_event", lambda kind, event: emitted.append(event))
    monkeypatch.setattr(upload, "_upload_redirect_html", lambda *args: True)
    monkeypatch.setattr(upload, "refresh_public_photo_manifest", lambda **kwargs: True)
    monkeypatch.setattr(upload, "_upload_local_path_to_s3", lambda *args: subprocess.CompletedProcess([], 1, b"", b"offline"))
    assert upload.retry_pending_uploads()["failed"] == 1
    assert not emitted
    assert Path(pending.file_path).exists()
    monkeypatch.setattr(upload, "_upload_local_path_to_s3", lambda *args: subprocess.CompletedProcess([], 0, b"", b""))
    assert upload.retry_pending_uploads()["succeeded"] == 1
    assert len(emitted) == 1 and emitted[0]["success"]
    assert emitted[0]["url"] == info.full_url
    assert not Path(pending.file_path).exists()


def test_pending_photo_is_not_counted_as_failed(monkeypatch):
    from artifact.telegram.bot import StatsReader

    reader = StatsReader()
    monkeypatch.setattr(reader, "photo_events", lambda *args: [{"short_id": "pending", "success": False, "queued": True}])
    monkeypatch.setattr(reader, "_count_ai_logs", lambda *args: (0, 0))
    monkeypatch.setattr(reader, "pending_uploads", lambda: 1)
    stats = reader.build_stats()
    assert stats["photos"] == 1
    assert stats["successful_photos"] == stats["failed_photos"] == 0
    assert stats["pending_uploads"] == 1


def test_daemon_cannot_delete_foreground_payload(monkeypatch, spool):
    """Reproduce the live race: retry starts while foreground is uploading."""
    calls = []
    def foreground(path, *args, **kwargs):
        calls.append(path)
        assert upload.retry_pending_uploads() == {"retried": 0, "succeeded": 0, "failed": 0}
        assert Path(path).read_bytes() == b"photo in flight"
        return subprocess.CompletedProcess([], 1, b"", b"connection closed")
    monkeypatch.setattr(upload, "_upload_local_path_to_s3", foreground)
    result = upload.upload_bytes_to_s3(b"photo in flight", "photobooth")
    assert result.queued and not result.success
    assert len(calls) == 1
    assert len(list((spool / "photobooth").glob("*.json"))) == 1


def test_job_lock_coordinates_separate_processes_and_releases_after_crash(spool):
    import os
    import sys
    code = '''
import os, sys
from pathlib import Path
from artifact.utils import s3_upload as upload
upload.UPLOAD_SPOOL_DIR = Path(sys.argv[1])
with upload._upload_job_lock("photobooth", "same.png", blocking=False) as acquired:
    print(acquired, flush=True)
    if acquired:
        os._exit(0)
'''
    with upload._upload_job_lock("photobooth", "same.png"):
        child = subprocess.run([sys.executable, "-c", code, str(spool)], capture_output=True, text=True, check=True)
        assert child.stdout.strip().endswith("False")
    child = subprocess.run([sys.executable, "-c", code, str(spool)], capture_output=True, text=True, check=True)
    assert child.stdout.strip().endswith("True")
    with upload._upload_job_lock("photobooth", "same.png", blocking=False) as acquired:
        assert acquired
