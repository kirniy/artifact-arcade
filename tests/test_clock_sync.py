import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "clock_sync", Path(__file__).parents[1] / "scripts/sync-clock-https.py",
)
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


def test_agreement_accounts_for_elapsed_time():
    assert clock.agreed_time([(1000, 10), (1005, 15)], 20) == 1010


@pytest.mark.parametrize("samples", [[], [(1000, 10)], [(1000, 10), (2000, 10)]])
def test_single_or_disagreeing_source_cannot_change_clock(samples):
    with pytest.raises(ValueError):
        clock.agreed_time(samples, 20)


def test_outlier_does_not_override_two_agreeing_sources():
    assert clock.agreed_time([(2000, 10), (1000, 10), (1002, 10)], 20) == 1011


@pytest.mark.parametrize("offset, expected", [(2, False), (300000, True), (-300000, True)])
def test_clock_is_only_set_for_large_confirmed_drift(monkeypatch, offset, expected):
    monkeypatch.setattr(clock, "sample_time", lambda url: (1000 + offset, 10))
    monkeypatch.setattr(clock.time, "monotonic", lambda: 10)
    monkeypatch.setattr(clock.time, "time", lambda: 1000)
    calls = []
    monkeypatch.setattr(clock.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    clock.main()
    assert bool(calls) == expected
