import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from artifact.modes.ticketscloud_theme_schedule import EventFeed, normalize_events, select_theme, SPB_VENUE, SPB_ORG, open_event_feed


def event(title="ВСЕ СВОИ | VNVNC", date="20261004T200000Z", **changes):
    return {"id": "test", "title": {"text": title}, "venue": SPB_VENUE, "org": SPB_ORG,
            "status": "public", "removed": False,
            "lifetime": f"BEGIN:VEVENT\r\nDTSTART;VALUE=DATE-TIME:{date}\r\nEND:VEVENT\r\n", **changes}


@pytest.mark.parametrize("instant,target", [
    ("2026-10-04T22:59:59+03:00", "night-riders"),
    ("2026-10-04T23:00:00+03:00", "vse-svoi"),
    ("2026-10-05T00:00:00+03:00", "vse-svoi"),
    ("2026-10-05T06:59:59+03:00", "vse-svoi"),
    ("2026-10-05T07:00:00+03:00", "night-riders"),
    ("2026-10-08T23:30:00+03:00", "night-riders"),  # Thursday alone is not an event.
])
def test_real_event_night_boundaries_and_timezone(instant, target):
    now = datetime.fromisoformat(instant)
    events = normalize_events([event()])
    assert select_theme(now, events, "night-riders") == target
    assert select_theme(now.astimezone(timezone.utc), events, "night-riders") == target


def test_any_weekday_and_cancelled_or_other_city_do_not_override():
    now = datetime.fromisoformat("2026-10-07T01:00:00+03:00")  # Tuesday party.
    events = normalize_events([event(date="20261006T200000Z")])
    assert select_theme(now, events, "night-riders") == "vse-svoi"
    for changes in ({"removed": True}, {"status": "cancelled"}, {"status": "draft"},
                    {"venue": "moscow"}, {"org": "other"}):
        assert normalize_events([event(**changes)]) == []
    assert normalize_events([event("ВСЕ СВОИМИ РУКАМИ")])[0]["vse_svoi"] is False


def test_cache_survives_cold_boot_and_network_failure(tmp_path, monkeypatch):
    cache = tmp_path / "events.json"
    events = normalize_events([event()])
    cache.write_text(json.dumps({"version": 1, "events": events}))
    feed = EventFeed(cache)
    monkeypatch.setenv("ARTIFACT_TICKETSCLOUD_API_KEY", "test-key")
    with patch("artifact.modes.ticketscloud_theme_schedule.open_event_feed", side_effect=TimeoutError):
        feed.refresh()
    assert feed.snapshot() == events
    rebooted = EventFeed(cache)
    assert select_theme(datetime.fromisoformat("2026-10-05T04:00:00+03:00"),
                        rebooted.snapshot(), "night-riders") == "vse-svoi"
    cache.write_text('{"version":1,"events":[{}]}')
    assert EventFeed(cache).snapshot() == []


def test_poll_never_blocks_or_starts_duplicate_fetches(tmp_path, monkeypatch):
    feed = EventFeed(tmp_path / "events.json")
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def slow_fetch():
        calls.append(1)
        entered.set()
        release.wait(2)
        finished.set()
    monkeypatch.setattr(feed, "refresh", slow_fetch)
    feed.poll()
    assert entered.wait(1)
    for _ in range(100):
        feed.poll()
        assert feed.snapshot() == []
    assert calls == [1]
    release.set()
    assert finished.wait(1)


def test_successful_refresh_updates_atomic_cache_and_removes_cancelled_event(tmp_path, monkeypatch):
    cache = tmp_path / "events.json"
    cache.write_text(json.dumps({"version": 1, "events": normalize_events([event()])}))
    feed = EventFeed(cache)
    monkeypatch.setenv("ARTIFACT_TICKETSCLOUD_API_KEY", "secret-test-key")
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps([event(status="cancelled")]).encode()
    with patch("artifact.modes.ticketscloud_theme_schedule.open_event_feed", return_value=Response()):
        feed.refresh()
    assert feed.snapshot() == []
    assert EventFeed(cache).snapshot() == []
    assert "secret-test-key" not in cache.read_text()
    assert not list(tmp_path.glob(".club-events-*"))


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        select_theme(datetime(2026, 10, 4, 23), [], "night-riders")


def test_direct_route_failure_uses_existing_gateway_without_losing_events(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_TICKETSCLOUD_API_KEY", "secret-test-key")
    feed = EventFeed(tmp_path / "cache.json")
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps([event()]).encode()
    with patch("artifact.modes.ticketscloud_theme_schedule.open_event_feed", side_effect=[ConnectionError(), Response()]) as request:
        assert feed.refresh() is True
    assert request.call_count == 2
    assert "apigw.yandexcloud.net/tc/v1/resources/events" in request.call_args.args[0].full_url
    assert feed.snapshot() == normalize_events([event()])
    assert "secret-test-key" not in feed.cache_path.read_text()


def test_event_http_does_not_use_global_ai_proxy(monkeypatch):
    monkeypatch.setenv("https_proxy", "http://ai-only-proxy.invalid:8080")
    with patch("urllib.request.build_opener") as build:
        open_event_feed("request")
    assert build.call_args.args[0].proxies == {}
    build.return_value.open.assert_called_once_with("request", timeout=10)
