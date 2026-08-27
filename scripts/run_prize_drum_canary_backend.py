#!/usr/bin/env python3
"""Loopback-only signed canary backend for physical prize-drum/RP80 soak.

This server never talks to the VNVNC database, Telegram, the staff scanner or
production APIs.  Every coupon starts with ``TEST-`` and every receipt terms
line says that it is invalid.  It exists solely to exercise the real cabinet,
network client, animation and RP80 printer without issuing a real prize.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import time
from typing import Any, Mapping
import uuid

from aiohttp import web


MAX_CLOCK_SKEW_SECONDS = 60
REGULAR_WHEEL_URL = "https://t.me/vnvncbattlebot?start=wheel"
TEST_TERMS = "ТЕСТОВЫЙ ЧЕК — НЕ ДЕЙСТВИТЕЛЕН. НЕ ПРИНИМАТЬ КАК ПРИЗ."
PRIZES = (
    ("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ"),
    ("DEP1K", "ДЕПОЗИТ 1 000 ₽"),
    ("DEP2K", "ДЕПОЗИТ 2 000 ₽"),
    ("MERCHFREE", "БЕСПЛАТНЫЙ МЕРЧ"),
    ("SHOT1FREE", "БЕСПЛАТНЫЙ ШОТ"),
    ("SHOTFR", "СЕТ ШОТОВ"),
    ("TIX1FREE", "БИЛЕТ НА ОДНОГО"),
    ("TIX50", "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ"),
)


class CanaryError(RuntimeError):
    def __init__(self, code: str, *, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class CanarySession:
    id: str
    auth_mode: str
    used: int = 0


@dataclass
class CanaryState:
    device_id: str
    secret: bytes
    sessions: dict[str, CanarySession] = field(default_factory=dict)
    responses_by_request: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    seen_nonces: dict[str, int] = field(default_factory=dict)
    award_sequence: int = 0

    def verify_signature(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str],
        now_timestamp: int | None = None,
    ) -> None:
        supplied_device = str(headers.get("X-Artifact-Device-ID", ""))
        supplied_timestamp = str(headers.get("X-Artifact-Timestamp", ""))
        nonce = str(headers.get("X-Artifact-Nonce", ""))
        supplied_signature = str(headers.get("X-Artifact-Signature", ""))
        if supplied_device != self.device_id:
            raise CanaryError("UNAUTHORIZED", status=401)
        try:
            timestamp = int(supplied_timestamp)
        except (TypeError, ValueError) as exc:
            raise CanaryError("INVALID_TIMESTAMP", status=401) from exc
        current = int(time.time()) if now_timestamp is None else int(now_timestamp)
        if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
            raise CanaryError("STALE_TIMESTAMP", status=401)
        if not nonce or len(nonce) > 128 or nonce in self.seen_nonces:
            raise CanaryError("REPLAYED_NONCE", status=409)

        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join(
            (method.upper(), path, supplied_timestamp, nonce, body_hash)
        ).encode("utf-8")
        expected = hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected):
            raise CanaryError("INVALID_SIGNATURE", status=401)

        self.seen_nonces[nonce] = timestamp
        stale_before = current - MAX_CLOCK_SKEW_SECONDS * 2
        self.seen_nonces = {
            value: seen_at
            for value, seen_at in self.seen_nonces.items()
            if seen_at >= stale_before
        }

    def create_session(self, *, request_id: str, auth_mode: str) -> dict[str, Any]:
        if auth_mode not in {"telegram", "guest"}:
            raise CanaryError("INVALID_AUTH_MODE")
        if not request_id or len(request_id) > 128:
            raise CanaryError("INVALID_REQUEST_ID")
        session_id = f"canary-{uuid.uuid5(uuid.NAMESPACE_URL, request_id).hex[:24]}"
        session = self.sessions.get(session_id)
        idempotent = session is not None
        if session is None:
            session = CanarySession(session_id, auth_mode)
            self.sessions[session_id] = session
        return {
            "success": True,
            "idempotent": idempotent,
            "session": self.session_payload(session),
        }

    def session_payload(self, session: CanarySession) -> dict[str, Any]:
        authenticated = False
        total = 1
        return {
            "id": session.id,
            "status": "READY" if session.auth_mode == "guest" else "AUTH_PENDING",
            "auth_mode": session.auth_mode,
            "club_night": "CANARY",
            "authenticated": authenticated,
            "user": None,
            "allowance": {
                "base": 1,
                "bonus": 0,
                "total": total,
                "used": session.used,
                "left": max(0, total - session.used),
                "active_boosts": 0,
            },
        }

    def spin(self, *, session_id: str, request_id: str) -> dict[str, Any]:
        key = (session_id, request_id)
        if key in self.responses_by_request:
            replay = dict(self.responses_by_request[key])
            replay["idempotent"] = True
            return replay
        session = self.sessions.get(session_id)
        if session is None:
            raise CanaryError("SESSION_NOT_FOUND", status=404)
        if session.auth_mode != "guest":
            raise CanaryError("CANARY_PRESS_6_FOR_GUEST", status=409)
        if session.used >= 1:
            raise CanaryError("NO_SPINS_LEFT", status=409)
        if not request_id or len(request_id) > 128:
            raise CanaryError("INVALID_REQUEST_ID")

        self.award_sequence += 1
        session.used += 1
        prize_id, prize_label = PRIZES[(self.award_sequence - 1) % len(PRIZES)]
        issued = datetime.now().astimezone()
        expiry = issued + timedelta(hours=1)
        issue_id = f"canary-issue-{self.award_sequence:06d}"
        coupon_code = f"TEST-VNVNC-{self.award_sequence:06d}"
        is_text_code = prize_id == "TIX50"
        flat = {
            "issue_id": issue_id,
            "prize_id": prize_id,
            "prize_title": prize_label,
            "prize_label": prize_label,
            "prize_description": TEST_TERMS,
            "terms": TEST_TERMS,
            "coupon_code": coupon_code,
            "redeem_qr_payload": "" if is_text_code else coupon_code,
            "redemption_method": "text_code" if is_text_code else "staff_qr",
            "show_prize_qr": not is_text_code,
            "redeemable_via_staff": not is_text_code,
            "text_promo_code": coupon_code if is_text_code else None,
            "issued_at": issued.isoformat(),
            "expires_at": expiry.isoformat(),
            "validity_slots": [],
            "regular_wheel_qr_payload": REGULAR_WHEEL_URL,
            "source_credit": "CANARY",
            "test_mode": True,
        }
        response = {
            "success": True,
            "idempotent": False,
            **flat,
            "award": dict(flat),
            "session": self.session_payload(session),
        }
        self.responses_by_request[key] = response
        return response

    def finish(self, session_id: str) -> dict[str, Any]:
        self.sessions.pop(session_id, None)
        return {"success": True}


def _json_body(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanaryError("INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise CanaryError("INVALID_JSON")
    return value


def create_app(state: CanaryState) -> web.Application:
    app = web.Application(client_max_size=64 * 1024)

    @web.middleware
    async def signed_request(request: web.Request, handler):
        body = await request.read()
        try:
            state.verify_signature(
                method=request.method,
                path=request.path,
                body=body,
                headers=request.headers,
            )
            request["raw_body"] = body
            return await handler(request)
        except CanaryError as exc:
            return web.json_response(
                {"success": False, "error": exc.code, "message": "CANARY REQUEST REJECTED"},
                status=exc.status,
            )

    app.middlewares.append(signed_request)

    async def create_session(request: web.Request) -> web.Response:
        payload = _json_body(request["raw_body"])
        return web.json_response(state.create_session(
            request_id=str(payload.get("request_id", "")),
            auth_mode=str(payload.get("auth_mode", "")),
        ))

    async def get_session(request: web.Request) -> web.Response:
        session = state.sessions.get(request.match_info["session_id"])
        if session is None:
            raise CanaryError("SESSION_NOT_FOUND", status=404)
        return web.json_response({"success": True, "session": state.session_payload(session)})

    async def start_auth(_request: web.Request) -> web.Response:
        return web.json_response({
            "success": True,
            "pairing_id": "CANARY-ONLY",
            "auth_url": "https://example.invalid/vnvnc-canary-press-6",
        })

    async def spin(request: web.Request) -> web.Response:
        payload = _json_body(request["raw_body"])
        return web.json_response(state.spin(
            session_id=request.match_info["session_id"],
            request_id=str(payload.get("request_id", "")),
        ))

    async def finish(request: web.Request) -> web.Response:
        return web.json_response(state.finish(request.match_info["session_id"]))

    async def error_boundary(request: web.Request, handler):
        try:
            return await handler(request)
        except CanaryError as exc:
            return web.json_response(
                {"success": False, "error": exc.code, "message": exc.code},
                status=exc.status,
            )

    app.middlewares.insert(0, web.middleware(error_boundary))
    app.router.add_post("/api/artifact-kiosk/session", create_session)
    app.router.add_get("/api/artifact-kiosk/session/{session_id}", get_session)
    app.router.add_post("/api/artifact-kiosk/session/{session_id}/auth/start", start_auth)
    app.router.add_post("/api/artifact-kiosk/session/{session_id}/spin", spin)
    app.router.add_post("/api/artifact-kiosk/session/{session_id}/finish", finish)
    return app


def _required_setting(name: str) -> str:
    value = str(os.getenv(name, "")).strip()
    if not value:
        raise SystemExit(f"{name} is required (value is never printed)")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Canary backend is loopback-only")
    device_id = _required_setting("ARTIFACT_KIOSK_DEVICE_ID")
    secret = _required_setting("ARTIFACT_KIOSK_DEVICE_SECRET")
    if len(secret) < 24:
        raise SystemExit("ARTIFACT_KIOSK_DEVICE_SECRET must be at least 24 characters")
    state = CanaryState(device_id=device_id, secret=secret.encode("utf-8"))
    print(f"CANARY ONLY · TEST COUPONS · listening on {args.host}:{args.port}")
    web.run_app(create_app(state), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
