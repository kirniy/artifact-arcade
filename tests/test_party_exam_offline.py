from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import asyncio
import base64
import hashlib
import hmac
from io import BytesIO
import json
import os
import struct
import time
import uuid

import numpy as np
from PIL import Image
import pytest

from artifact.core.events import Event, EventType
from artifact.modes.party_exam import PartyExamMode
from artifact.printing.party_exam_roll import PartyExamRollReceiptGenerator
from artifact.utils.party_exam_offline import (
    OfflineCards, MOSCOW, encode_token, night_for_timestamp, sync_once,
)
from test_spiderverse_quest import _context

AT = datetime(2026, 9, 18, 23, 30, tzinfo=MOSCOW).timestamp()
SECRET = "offline-test-key-no-real-credentials"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PARTY_EXAM_PRIVATE_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("ARTIFACT_KIOSK_DEVICE_ID", "test-device")
    monkeypatch.setenv("ARTIFACT_KIOSK_DEVICE_SECRET", SECRET)
    result = OfflineCards(tmp_path / "jobs")
    result.configure(allocation(result.provision_id()), device_id="test-device")
    return result


def allocation(allocation_id, first=26091841, last=26191840):
    return dict(success=True, scheme="exam-offline-v1", allocation_id=allocation_id,
                device_id="test-device", first_number=first, last_number=last,
                nights=["2026-09-18", "2026-09-19"])


def picture():
    output = BytesIO()
    Image.new("RGB", (640, 480), (170, 145, 100)).save(output, "JPEG")
    return output.getvalue()


def saved_source(mode):
    path = mode._private_root() / mode._quest_print_id / "source.jpg"
    mode._save_private(path, picture())
    os.utime(path, (AT, AT))
    return path


def test_token_contract_and_telegram_length():
    token = encode_token(26091841, int(AT), "test-device", SECRET)
    raw = base64.urlsafe_b64decode(token)
    assert struct.unpack(">II", raw[:8]) == (26091841, int(AT))
    expected = hmac.new(SECRET.encode(), b"party-exam-offline-v1\0test-device\0" + raw[:8], hashlib.sha256).digest()[:16]
    assert raw[8:] == expected
    assert len(token) == 32 and len("exam_" + token) <= 64


def test_offline_token_fixed_cross_repo_vector():
    stamp = int(datetime(2026, 9, 18, 23, 30, tzinfo=MOSCOW).timestamp())
    token = encode_token(26091841, stamp, "artifact-test", "cross-contract-secret-123")
    assert token == "AY4hQWqtn0jJsMjfNfmOUgyX6_N3gFRQ"


def test_reopen_and_allocation_replay_do_not_reuse_numbers(store):
    job = uuid.uuid4().hex
    card = store.reserve(job, issued_at=AT)
    with store.connect() as db:
        block = dict(db.execute("SELECT * FROM allocations").fetchone())
    reopened = OfflineCards(store.root)
    reopened.configure(allocation(block["allocation_id"]), device_id="test-device")
    assert reopened.reserve(job, issued_at=AT + 10000) == card
    next_card = reopened.reserve(uuid.uuid4().hex, issued_at=AT + 1)
    assert next_card["student_number"] == card["student_number"] + 1
    assert reopened.status()["issued"] == 2


def test_concurrent_and_duplicate_allocation_is_atomic(store):
    ids = [uuid.uuid4().hex for _ in range(12)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        cards = list(pool.map(lambda job: store.reserve(job, issued_at=AT), ids + [ids[0]]))
    assert cards[0] == cards[-1]
    assert sorted({card["student_number"] for card in cards}) == list(range(26091841, 26091853))


@pytest.mark.parametrize("stamp,night", [
    ("2026-09-18T23:00:00+03:00", "2026-09-18"),
    ("2026-09-19T06:59:59+03:00", "2026-09-18"),
    ("2026-09-19T23:00:00+03:00", "2026-09-19"),
    ("2026-09-20T06:59:59+03:00", "2026-09-19"),
])
def test_offline_club_night_boundaries(stamp, night):
    assert night_for_timestamp(datetime.fromisoformat(stamp).timestamp()) == night


def test_capacity_and_campaign_fail_closed_without_duplicate_qr(store):
    with pytest.raises(ValueError, match="NIGHT_CLOSED"):
        store.reserve(uuid.uuid4().hex, issued_at=AT - 3600)
    with store.connect() as db:
        db.execute("UPDATE allocations SET next_number=last_number+1")
    with pytest.raises(ValueError, match="OFFLINE_CARDS_NOT_PROVISIONED"):
        store.reserve(uuid.uuid4().hex, issued_at=AT)
    assert store.status()["issued"] == 0


@pytest.mark.asyncio
async def test_network_failure_still_renders_personalized_qr_and_retry_is_identical(store, monkeypatch):
    class FailedAI:
        async def generate_image(self, **kwargs):
            raise ConnectionError("network disconnected")
    monkeypatch.setattr("artifact.modes.party_exam.get_gemini_client", lambda: FailedAI())
    monkeypatch.setattr("artifact.services.vnvnc_kiosk.VNVNCKioskClient._request",
                        lambda *a, **k: pytest.fail("Receipt issuance contacted backend"))
    mode = PartyExamMode(_context()); mode.enter(); mode._start_quest_photo()
    mode._state.photo_bytes = picture(); saved_source(mode)
    result = await mode._generate_photobooth_grid()
    mode._state.ai_label_bytes = result[1]; mode._state.show_result = True
    mode._start_printing_now()
    jobs = mode.context.event_bus.get_history(EventType.PRINT_START)
    assert len(jobs) == 1
    original = jobs[0].data
    receipt = PartyExamRollReceiptGenerator().generate_receipt("photobooth", original)
    import cv2
    url, _, _ = cv2.QRCodeDetector().detectAndDecode(np.asarray(Image.open(BytesIO(receipt.preview_image))))
    assert url == mode._student["claim_url"]
    assert store.status()["pending"] == 1
    mode.on_input(Event(EventType.PRINT_ERROR, {"issue_id": mode._quest_print_id}))
    mode.on_input(Event(EventType.BUTTON_PRESS, {}))
    again = mode.context.event_bus.get_history(EventType.PRINT_START)[-1].data
    assert again["claim_url"] == original["claim_url"]
    assert again["student_number"] == original["student_number"]
    assert store.status()["issued"] == 1


@pytest.mark.asyncio
async def test_ai_timeout_is_bounded_and_fallback_saved_before_wait(store, monkeypatch):
    mode = PartyExamMode(_context()); mode.enter(); mode._start_quest_photo()
    mode._state.photo_bytes = picture(); source = saved_source(mode)
    class SlowAI:
        async def generate_image(self, **kwargs):
            assert source.with_name("student.json").exists()
            assert source.with_name("portrait.png").exists()
            await asyncio.sleep(30)
    monkeypatch.setattr("artifact.modes.party_exam.get_gemini_client", lambda: SlowAI())
    monkeypatch.setenv("PARTY_EXAM_AI_TIMEOUT_SECONDS", "1")
    started = time.monotonic()
    assert await mode._generate_photobooth_grid()
    assert time.monotonic() - started < 2
    assert store.status()["pending"] == 1


@pytest.mark.asyncio
async def test_lost_upload_ack_retries_same_token_after_reopen(store):
    job_id = uuid.uuid4().hex
    card = store.reserve(job_id, issued_at=AT)
    path = store.root / job_id / "portrait.png"
    PartyExamMode._save_private(path, picture()); store.ready(job_id, path)
    calls = []
    class API:
        async def _request(self, method, endpoint, payload):
            calls.append(payload)
            if len(calls) == 1:
                raise TimeoutError("committed server response lost")
            return {"success": True, **card}
    api = API()
    assert await sync_once(store, api) == {"synced": 0, "deferred": 1}
    with store.connect() as db:
        db.execute("UPDATE jobs SET next_attempt_at=0")
    reopened = OfflineCards(store.root)
    assert await sync_once(reopened, api) == {"synced": 1, "deferred": 0}
    assert calls[0] == calls[1]
    assert reopened.status()["synced"] == 1
    assert await sync_once(reopened, api) == {"synced": 0, "deferred": 0}


@pytest.mark.asyncio
async def test_wrong_upload_identity_does_not_drop_pending_portrait(store):
    job_id = uuid.uuid4().hex; card = store.reserve(job_id, issued_at=AT)
    path = store.root / job_id / "portrait.png"
    PartyExamMode._save_private(path, picture()); store.ready(job_id, path)
    class API:
        async def _request(self, *args):
            return {"success": True, **card, "student_number": 123}
    assert (await sync_once(store, API()))["deferred"] == 1
    assert store.status()["pending"] == 1


def test_saved_card_can_restore_missing_database_row_without_new_identity(store):
    job_id = uuid.uuid4().hex
    card = store.reserve(job_id, issued_at=AT)
    folder = store.root / job_id
    for name, data in [("source.jpg", picture()), ("portrait.png", picture()),
                       ("student.json", json.dumps(card).encode())]:
        PartyExamMode._save_private(folder / name, data)
    with store.connect() as db:
        db.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
    recovered = PartyExamMode(_context()); recovered.enter()
    assert recovered._quest_print_id == job_id
    assert recovered._student == card and recovered._print_error
    assert store.status()["issued"] == 1 and store.status()["pending"] == 1
    recovered.on_input(Event(EventType.BUTTON_PRESS, {}))
    assert recovered.context.event_bus.get_history(EventType.PRINT_START)[-1].data["claim_url"] == card["claim_url"]


def test_sync_recovery_does_not_publish_in_progress_ai_fallback(store):
    job_id = uuid.uuid4().hex; card = store.reserve(job_id, issued_at=AT)
    folder = store.root / job_id
    for name, data in [("portrait.png", picture()), ("student.json", json.dumps(card).encode())]:
        PartyExamMode._save_private(folder / name, data)
    assert store.recover_saved_cards() == 0
    assert store.status()["pending"] == 0
    PartyExamMode._save_private(folder / "receipt-ready", b"final")
    assert store.recover_saved_cards() == 1
    assert store.status()["pending"] == 1
