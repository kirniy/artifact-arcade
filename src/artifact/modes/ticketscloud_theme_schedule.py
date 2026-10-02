"""Non-blocking Tickets Cloud club-night selection with a durable offline cache."""
import json
import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
import urllib.request
from datetime import datetime, time as clock_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")
SPB_VENUE = "632a5e73c04811e5fd44bbde"
SPB_ORG = "63206ee78749097c592a6697"


def normalize_events(payload):
    """Keep only published SPb event dates/titles; no descriptions or credentials."""
    if not isinstance(payload, list):
        raise ValueError("Tickets Cloud must return an event list")
    events = []
    for event in payload:
        if not isinstance(event, dict):
            continue
        if event.get("venue") != SPB_VENUE or event.get("org") != SPB_ORG:
            continue
        if event.get("removed") or event.get("status") not in {"public", "finished", "active"}:
            continue
        title = event.get("title", {})
        title = title.get("text", "") if isinstance(title, dict) else str(title)
        # The live v1 feed supplies UTC iCalendar DTSTART values.
        match = re.search(r"^DTSTART(?:;[^:\r\n]*)?:(\d{8}T\d{6}Z)\s*$",
                          str(event.get("lifetime", "")), re.MULTILINE)
        if not match:
            continue
        start = datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        day = start.astimezone(MOSCOW).date()
        if start.astimezone(MOSCOW).hour < 7:
            day -= timedelta(days=1)
        clean_title = unicodedata.normalize("NFKC", title).upper().replace("Ё", "Е")
        vse_svoi = bool(re.search(r"\bВСЕ\s+СВОИ\b", clean_title))
        events.append({"id": str(event.get("id", "")), "date": day.isoformat(),
                       "title": title, "vse_svoi": vse_svoi})
    return events


def select_theme(now, events, default_theme):
    if now.tzinfo is None:
        raise ValueError("Schedule requires a timezone-aware clock")
    local = now.astimezone(MOSCOW)
    day = local.date() - timedelta(days=1) if local.hour < 7 else local.date()
    start = datetime.combine(day, clock_time(23), MOSCOW)
    end = datetime.combine(day + timedelta(days=1), clock_time(7), MOSCOW)
    if start <= local < end and any(e.get("date") == day.isoformat() and e.get("vse_svoi") is True
                                  for e in events):
        return "vse-svoi"
    return default_theme


class EventFeed:
    """Read cached events at boot; fetch on a daemon thread, never the UI loop."""
    def __init__(self, cache_path=None):
        self.cache_path = Path(cache_path or os.getenv("ARTIFACT_CLUB_EVENTS_CACHE",
            str(Path(__file__).resolve().parents[3] / ".deploy/club-events.json")))
        self._lock = threading.Lock()
        self._events = []
        self._next_poll = 0.0
        self._fetching = False
        try:
            saved = json.loads(self.cache_path.read_text())
            if isinstance(saved, dict) and saved.get("version") == 1 and isinstance(saved.get("events"), list):
                # Validate cached values so a damaged file cannot crash the menu.
                for event in saved["events"]:
                    datetime.strptime(event["date"], "%Y-%m-%d")
                    assert isinstance(event["vse_svoi"], bool)
                self._events = saved["events"]
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            pass

    def snapshot(self):
        with self._lock:
            return list(self._events)

    def poll(self):
        with self._lock:
            if self._fetching or time.monotonic() < self._next_poll:
                return
            self._fetching = True
            self._next_poll = time.monotonic() + 300
        threading.Thread(target=self.refresh, name="club-events", daemon=True).start()

    def refresh(self):
        try:
            key = os.getenv("ARTIFACT_TICKETSCLOUD_API_KEY", "").strip()
            if not key:
                raise ValueError("ARTIFACT_TICKETSCLOUD_API_KEY is missing")
            request = urllib.request.Request("https://ticketscloud.com/v1/resources/events",
                                            headers={"Authorization": "key " + key})
            with urllib.request.urlopen(request, timeout=10) as response:
                events = normalize_events(json.loads(response.read(4 * 1024 * 1024)))
            payload = {"version": 1, "fetched_at": datetime.now(timezone.utc).isoformat(),
                       "events": events}
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".club-events-", dir=self.cache_path.parent)
            try:
                with os.fdopen(fd, "w") as output:
                    json.dump(payload, output, ensure_ascii=False)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.cache_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            with self._lock:
                self._events = events
            logger.info("Tickets Cloud schedule refreshed: %d SPb events", len(events))
            return True
        except Exception as error:
            # Never log request URLs/headers or provider response bodies with secrets.
            logger.warning("Tickets Cloud schedule refresh failed (%s); retaining cached events",
                           type(error).__name__)
            with self._lock:
                self._next_poll = time.monotonic() + 60
            return False
        finally:
            with self._lock:
                self._fetching = False


_feed = None


def scheduled_theme(now=None):
    global _feed
    if _feed is None:
        _feed = EventFeed()
    _feed.poll()
    default = os.getenv("PHOTOBOOTH_DEFAULT_THEME", os.getenv("PHOTOBOOTH_THEME", "night-riders"))
    return select_theme(now or datetime.now(MOSCOW), _feed.snapshot(), default)
