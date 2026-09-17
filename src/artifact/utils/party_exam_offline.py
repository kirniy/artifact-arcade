"""Durable local student cards and an independent, retryable portrait outbox."""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import struct
import time
import uuid
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

log = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")
NIGHTS = ("2026-09-18", "2026-09-19")
SCHEME = "exam-offline-v1"
DOMAIN = b"party-exam-offline-v1\0"


def private_root() -> Path:
    return Path(os.environ.get(
        "PARTY_EXAM_PRIVATE_DIR", str(Path.home() / ".local/share/artifact/party-exam")
    ))


def night_for_timestamp(timestamp: float) -> str:
    current = datetime.fromtimestamp(timestamp, MOSCOW)
    day = current.date() - timedelta(days=1) if current.hour < 7 else current.date()
    if day.isoformat() not in NIGHTS or not (current.hour >= 23 or current.hour < 7):
        raise ValueError("NIGHT_CLOSED")
    return day.isoformat()


def encode_token(number: int, timestamp: int, device_id: str, secret: str) -> str:
    if not device_id or len(secret) < 16:
        raise ValueError("OFFLINE_SIGNING_NOT_CONFIGURED")
    body = struct.pack(">II", number, timestamp)
    signature = hmac.new(
        secret.encode(), DOMAIN + device_id.encode() + b"\0" + body, hashlib.sha256
    ).digest()[:16]
    return base64.urlsafe_b64encode(body + signature).decode("ascii")


def card_from_row(row) -> dict:
    night = row["night"]
    draw = datetime.fromisoformat(night).replace(tzinfo=MOSCOW) + timedelta(days=1, hours=4)
    return {
        "student_number": row["student_number"], "night": night,
        "claim_url": "https://t.me/vnvncbattlebot?start=exam_" + row["claim_token"],
        "draw_at": draw.isoformat(), "offline": True,
    }


class OfflineCards:
    """Allocate once, commit before print, and never reset a reserved number range."""

    def __init__(self, root: Path | None = None):
        self.root = root or private_root()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "offline.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS allocations (
                    allocation_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
                    first_number INTEGER NOT NULL, last_number INTEGER NOT NULL,
                    next_number INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, claim_token TEXT NOT NULL UNIQUE,
                    student_number INTEGER NOT NULL UNIQUE, night TEXT NOT NULL,
                    issued_at INTEGER NOT NULL, portrait_path TEXT,
                    synced_at REAL, attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL DEFAULT 0, last_error TEXT
                );
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def remaining(self) -> int:
        with self.connect() as db:
            return db.execute(
                "SELECT COALESCE(SUM(MAX(0,last_number-next_number+1)),0) FROM allocations"
            ).fetchone()[0]

    def provision_id(self) -> str:
        # Persist the request identity before contacting the server. Retrying a
        # timed-out allocation must return that same range, not consume another.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM meta WHERE key='pending_allocation'").fetchone()
            if row:
                return row[0]
            value = uuid.uuid4().hex
            db.execute("INSERT INTO meta VALUES ('pending_allocation',?)", (value,))
            return value

    def configure(self, data: dict, *, device_id: str) -> None:
        allocation_id = data["allocation_id"]
        first, last = int(data["first_number"]), int(data["last_number"])
        if (data.get("scheme") != SCHEME or data.get("device_id") != device_id
                or data.get("nights") != list(NIGHTS)
                or not re.fullmatch(r"[a-f0-9]{32}", allocation_id)
                or not 0 < first <= last < 2**31):
            raise ValueError("INVALID_OFFLINE_ALLOCATION")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM allocations WHERE allocation_id=?", (allocation_id,)).fetchone()
            if old:
                if (old["device_id"], old["first_number"], old["last_number"]) != (device_id, first, last):
                    raise ValueError("OFFLINE_ALLOCATION_CONFLICT")
                # Deliberately leave next_number untouched on a repeated response.
            else:
                if db.execute("SELECT 1 FROM allocations WHERE first_number<=? AND last_number>=?", (last, first)).fetchone():
                    raise ValueError("OVERLAPPING_OFFLINE_ALLOCATION")
                db.execute("INSERT INTO allocations VALUES (?,?,?,?,?)", (allocation_id, device_id, first, last, first))
            db.execute("DELETE FROM meta WHERE key='pending_allocation' AND value=?", (allocation_id,))

    def reserve(self, job_id: str, *, issued_at: float | None = None) -> dict:
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("INVALID_LOCAL_JOB")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if old:
                return card_from_row(old)
            timestamp = int(time.time() if issued_at is None else issued_at)
            night = night_for_timestamp(timestamp)
            device_id = os.getenv("ARTIFACT_KIOSK_DEVICE_ID", "").strip()
            allocation = db.execute(
                "SELECT * FROM allocations WHERE device_id=? AND next_number<=last_number ORDER BY first_number LIMIT 1",
                (device_id,),
            ).fetchone()
            if not allocation:
                raise ValueError("OFFLINE_CARDS_NOT_PROVISIONED")
            number = allocation["next_number"]
            token = encode_token(number, timestamp, device_id, os.getenv("ARTIFACT_KIOSK_DEVICE_SECRET", "").strip())
            db.execute("UPDATE allocations SET next_number=next_number+1 WHERE allocation_id=?", (allocation["allocation_id"],))
            db.execute("INSERT INTO jobs (job_id,claim_token,student_number,night,issued_at) VALUES (?,?,?,?,?)",
                       (job_id, token, number, night, timestamp))
            return card_from_row(db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone())

    def ready(self, job_id: str, portrait_path: Path) -> None:
        path = portrait_path.resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise ValueError("INVALID_PRIVATE_PORTRAIT_PATH")
        with self.connect() as db:
            # The receipt image is immutable once queued, so a replay cannot
            # change a portrait already uploaded to the student's account.
            db.execute("UPDATE jobs SET portrait_path=? WHERE job_id=? AND portrait_path IS NULL", (str(path), job_id))
            if not db.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,)).fetchone():
                raise ValueError("OFFLINE_JOB_NOT_FOUND")

    def restore(self, job_id: str, card: dict) -> None:
        """Recover an already-issued signed card without allocating a new ID."""
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("INVALID_LOCAL_JOB")
        match = re.fullmatch(r"https://t.me/vnvncbattlebot\?start=exam_([A-Za-z0-9_-]{32})", str(card.get("claim_url", "")))
        if not match:
            raise ValueError("INVALID_SAVED_OFFLINE_CARD")
        token = match.group(1)
        raw = base64.urlsafe_b64decode(token)
        number, timestamp = struct.unpack(">II", raw[:8])
        device = os.getenv("ARTIFACT_KIOSK_DEVICE_ID", "").strip()
        expected = encode_token(number, timestamp, device, os.getenv("ARTIFACT_KIOSK_DEVICE_SECRET", "").strip())
        night = night_for_timestamp(timestamp)
        if (not hmac.compare_digest(token, expected) or card.get("student_number") != number
                or card.get("night") != night):
            raise ValueError("INVALID_SAVED_OFFLINE_CARD")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT claim_token FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if old:
                if old[0] != token:
                    raise ValueError("SAVED_OFFLINE_CARD_CONFLICT")
                return
            db.execute("INSERT INTO jobs (job_id,claim_token,student_number,night,issued_at) VALUES (?,?,?,?,?)",
                       (job_id, token, number, night, timestamp))
            db.execute("UPDATE allocations SET next_number=MAX(next_number,?) WHERE device_id=? AND first_number<=? AND last_number>=?",
                       (number + 1, device, number, number))

    def recover_saved_cards(self) -> int:
        recovered = 0
        for path in self.root.glob("*/student.json"):
            folder = path.parent
            if not (folder / "receipt-ready").exists() or not (folder / "portrait.png").is_file():
                continue
            try:
                card = json.loads(path.read_text())
                if not card.get("offline"):
                    continue
                self.restore(folder.name, card)
                self.ready(folder.name, folder / "portrait.png")
                recovered += 1
            except (ValueError, OSError, sqlite3.Error) as exc:
                log.warning("Saved offline receipt recovery deferred (%s)", type(exc).__name__)
        return recovered

    def due(self, limit: int = 20, *, now: float | None = None) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE synced_at IS NULL AND portrait_path IS NOT NULL AND next_attempt_at<=? ORDER BY next_attempt_at,issued_at,student_number LIMIT ?",
                (time.time() if now is None else now, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def acknowledge(self, job: dict, response: dict) -> None:
        expected = card_from_row(job)
        if (response.get("success") is not True or any(response.get(key) != expected[key]
                for key in ("student_number", "night", "claim_url"))):
            raise ValueError("OFFLINE_SYNC_IDENTITY_MISMATCH")
        with self.connect() as db:
            db.execute("UPDATE jobs SET synced_at=?,last_error=NULL WHERE job_id=? AND claim_token=?",
                       (time.time(), job["job_id"], job["claim_token"]))

    def defer(self, job: dict, error: Exception) -> None:
        attempts = job["attempts"] + 1
        delay = min(120, 5 * 2**min(attempts - 1, 5))
        with self.connect() as db:
            db.execute("UPDATE jobs SET attempts=?,next_attempt_at=?,last_error=? WHERE job_id=?",
                       (attempts, time.time() + delay, type(error).__name__, job["job_id"]))

    def status(self) -> dict:
        with self.connect() as db:
            return {"remaining": self.remaining(),
                    "issued": db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                    "pending": db.execute("SELECT COUNT(*) FROM jobs WHERE portrait_path IS NOT NULL AND synced_at IS NULL").fetchone()[0],
                    "synced": db.execute("SELECT COUNT(*) FROM jobs WHERE synced_at IS NOT NULL").fetchone()[0]}


def local_portrait(source: bytes) -> bytes:
    """A real camera portrait for thermal printing when AI cannot be reached."""
    with Image.open(io.BytesIO(source)) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        image = ImageOps.fit(image, (450, 600), centering=(0.5, 0.4))
        image = ImageOps.autocontrast(image, cutoff=1)
        image = image.point([int(255 * (value / 255)**0.72) for value in range(256)])
        output = io.BytesIO()
        image.save(output, "PNG", optimize=True)
        return output.getvalue()


def client():
    from artifact.services.vnvnc_kiosk import VNVNCKioskClient
    return VNVNCKioskClient(
        base_url=os.getenv("VNVNC_KIOSK_API_BASE_URL", "https://api.vnvnc.ru"),
        device_id=os.getenv("ARTIFACT_KIOSK_DEVICE_ID", ""),
        device_secret=os.getenv("ARTIFACT_KIOSK_DEVICE_SECRET", ""), timeout_seconds=10,
    )


async def provision(store: OfflineCards, api=None) -> None:
    if store.remaining() >= 1000:
        return
    api = api or client()
    response = await api._request("POST", "/api/party-exam/offline/provision", {"allocation_id": store.provision_id()})
    store.configure(response, device_id=os.getenv("ARTIFACT_KIOSK_DEVICE_ID", "").strip())


async def sync_once(store: OfflineCards, api=None) -> dict:
    api = api or client()
    done = failed = 0
    for job in store.due():
        try:
            portrait = Path(job["portrait_path"]).read_bytes()
            response = await api._request("POST", "/api/party-exam/offline/sync", {
                "claim_token": job["claim_token"], "portrait": base64.b64encode(portrait).decode("ascii"),
            })
            store.acknowledge(job, response)
            done += 1
        except Exception as exc:
            store.defer(job, exc)
            failed += 1
            log.warning("Student portrait synchronization deferred (%s)", type(exc).__name__)
    return {"synced": done, "deferred": failed}


async def main_async(command: str) -> None:
    store = OfflineCards()
    if command == "status":
        print(json.dumps(store.status()))
        return
    if command == "provision":
        await provision(store)
        print(json.dumps(store.status()))
        return
    if command == "sync-once":
        print(json.dumps(await sync_once(store)))
        return
    with (store.root / "offline-sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        next_provision = 0.0
        while True:
            if time.monotonic() >= next_provision:
                store.recover_saved_cards()
                try:
                    await provision(store)
                except Exception as exc:
                    log.warning("Offline number reservation deferred (%s); existing cards remain usable", type(exc).__name__)
                next_provision = time.monotonic() + 60
            await sync_once(store)
            await asyncio.sleep(5)


def main():
    from dotenv import load_dotenv
    load_dotenv(Path.cwd() / ".env")
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "provision", "sync", "sync-once"))
    asyncio.run(main_async(parser.parse_args().command))


if __name__ == "__main__":
    main()
