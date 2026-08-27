from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from aiohttp import web

from artifact.services.vnvnc_kiosk import VNVNCKioskClient, parse_spin_response


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_prize_drum_canary_backend.py"
SPEC = importlib.util.spec_from_file_location("prize_drum_canary_backend", SCRIPT)
assert SPEC and SPEC.loader
canary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = canary
SPEC.loader.exec_module(canary)


def _headers(secret: bytes, method: str, path: str, body: bytes, *, now: int, nonce: str):
    canonical = "\n".join((
        method,
        path,
        str(now),
        nonce,
        hashlib.sha256(body).hexdigest(),
    )).encode()
    return {
        "X-Artifact-Device-ID": "artifact-canary",
        "X-Artifact-Timestamp": str(now),
        "X-Artifact-Nonce": nonce,
        "X-Artifact-Signature": hmac.new(secret, canonical, hashlib.sha256).hexdigest(),
    }


def test_canary_signature_is_constant_time_checked_and_nonce_is_single_use() -> None:
    secret = b"canary-secret-that-is-long-enough"
    state = canary.CanaryState("artifact-canary", secret)
    body = json.dumps({"request_id": "session-1"}).encode()
    headers = _headers(secret, "POST", "/api/artifact-kiosk/session", body, now=1000, nonce="n1")
    state.verify_signature(
        method="POST",
        path="/api/artifact-kiosk/session",
        body=body,
        headers=headers,
        now_timestamp=1000,
    )
    with pytest.raises(canary.CanaryError, match="REPLAYED_NONCE"):
        state.verify_signature(
            method="POST",
            path="/api/artifact-kiosk/session",
            body=body,
            headers=headers,
            now_timestamp=1000,
        )


def test_canary_signature_rejects_wrong_secret_and_stale_timestamp() -> None:
    secret = b"canary-secret-that-is-long-enough"
    state = canary.CanaryState("artifact-canary", secret)
    body = b"{}"
    wrong = _headers(b"wrong-secret-that-is-long-enough", "POST", "/x", body, now=1000, nonce="n1")
    with pytest.raises(canary.CanaryError, match="INVALID_SIGNATURE"):
        state.verify_signature(method="POST", path="/x", body=body, headers=wrong, now_timestamp=1000)
    stale = _headers(secret, "POST", "/x", body, now=900, nonce="n2")
    with pytest.raises(canary.CanaryError, match="STALE_TIMESTAMP"):
        state.verify_signature(method="POST", path="/x", body=body, headers=stale, now_timestamp=1000)


def test_canary_award_is_idempotent_nonredeemable_and_cycles_catalog() -> None:
    state = canary.CanaryState("artifact-canary", b"canary-secret-that-is-long-enough")
    created = state.create_session(request_id="s1", auth_mode="guest")
    session_id = created["session"]["id"]
    first = state.spin(session_id=session_id, request_id="spin-1")
    replay = state.spin(session_id=session_id, request_id="spin-1")

    assert first["idempotent"] is False
    assert replay["idempotent"] is True
    assert replay["issue_id"] == first["issue_id"]
    assert replay["coupon_code"] == first["coupon_code"]
    assert first["coupon_code"].startswith("TEST-VNVNC-")
    assert first["redeem_qr_payload"] == first["coupon_code"]
    assert first["regular_wheel_qr_payload"] == "https://t.me/vnvncbattlebot?start=wheel"
    assert first["prize_description"] == canary.TEST_TERMS
    assert first["test_mode"] is True
    assert first["award"]["test_mode"] is True
    with pytest.raises(canary.CanaryError, match="NO_SPINS_LEFT"):
        state.spin(session_id=session_id, request_id="spin-2")

    second_session = state.create_session(request_id="s2", auth_mode="guest")["session"]["id"]
    second = state.spin(session_id=second_session, request_id="spin-2")
    assert second["prize_id"] != first["prize_id"]


def test_canary_cycles_the_exact_eight_sector_presentation_contract() -> None:
    state = canary.CanaryState("artifact-canary", b"canary-secret-that-is-long-enough")
    expected = (
        ("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ"),
        ("DEP1K", "ДЕПОЗИТ 1 000 ₽"),
        ("DEP2K", "ДЕПОЗИТ 2 000 ₽"),
        ("MERCHFREE", "БЕСПЛАТНЫЙ МЕРЧ"),
        ("SHOT1FREE", "БЕСПЛАТНЫЙ ШОТ"),
        ("SHOTFR", "СЕТ ШОТОВ"),
        ("TIX1FREE", "БИЛЕТ НА ОДНОГО"),
        ("TIX50", "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ"),
    )

    actual = []
    for index in range(len(expected)):
        session_id = state.create_session(
            request_id=f"catalog-session-{index}", auth_mode="guest"
        )["session"]["id"]
        award = state.spin(
            session_id=session_id, request_id=f"catalog-spin-{index}"
        )
        actual.append((award["prize_id"], award["prize_title"]))

    assert tuple(actual) == expected


def test_canary_tix50_is_text_code_only_and_parses_through_real_client_contract() -> None:
    state = canary.CanaryState("artifact-canary", b"canary-secret-that-is-long-enough")
    state.award_sequence = len(canary.PRIZES) - 1
    session_id = state.create_session(request_id="tix50-session", auth_mode="guest")[
        "session"
    ]["id"]

    payload = state.spin(session_id=session_id, request_id="tix50-spin")
    result = parse_spin_response(payload)

    assert result.award.prize.id == "TIX50"
    assert payload["redeem_qr_payload"] == ""
    assert payload["redemption_method"] == "text_code"
    assert payload["show_prize_qr"] is False
    assert payload["redeemable_via_staff"] is False
    assert payload["text_promo_code"] == payload["coupon_code"]
    assert result.award.coupon.redemption_method == "text_code"
    assert result.award.coupon.show_prize_qr is False
    assert result.award.coupon.redeemable_via_staff is False
    assert result.award.coupon.text_promo_code == payload["coupon_code"]


def test_canary_telegram_flow_never_impersonates_real_login() -> None:
    state = canary.CanaryState("artifact-canary", b"canary-secret-that-is-long-enough")
    created = state.create_session(request_id="tg", auth_mode="telegram")
    assert created["session"]["status"] == "AUTH_PENDING"
    assert created["session"]["authenticated"] is False
    with pytest.raises(canary.CanaryError, match="CANARY_PRESS_6_FOR_GUEST"):
        state.spin(session_id=created["session"]["id"], request_id="spin")


@pytest.mark.asyncio
async def test_real_signed_kiosk_client_round_trips_against_loopback_canary(monkeypatch) -> None:
    secret = "canary-secret-that-is-long-enough"
    state = canary.CanaryState("artifact-canary", secret.encode())
    runner = web.AppRunner(canary.create_app(state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    client = VNVNCKioskClient(
        base_url=f"http://127.0.0.1:{port}",
        device_id="artifact-canary",
        device_secret=secret,
    )
    try:
        session = await client.create_session(request_id="transport-session", auth_mode="guest")
        assert session.allowance.left == 1
        first = await client.spin(session.id, request_id="transport-spin")
        replay = await client.spin(session.id, request_id="transport-spin")
        assert first.award.id == replay.award.id
        assert first.award.coupon.code == replay.award.coupon.code
        assert first.award.coupon.code.startswith("TEST-VNVNC-")
        assert first.award.prize.description == canary.TEST_TERMS
        assert first.award.test_mode is True
        assert replay.idempotent is True
        await client.finish_session(session.id)
        assert session.id not in state.sessions
    finally:
        await runner.cleanup()
