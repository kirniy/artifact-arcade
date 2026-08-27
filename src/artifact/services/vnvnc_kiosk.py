"""Server-authoritative client for the ФОТОБУДКА ВИНОВНИЦЫ prize drum.

Production requests are authenticated with a per-device HMAC.  The client never
sends a prize, coupon, expiry, weight, or Telegram identity; those values only
arrive in the signed-backend response after an award is committed.

``LocalKioskStub`` exists for simulator and automated UI testing only.  Hardware
mode fails closed when the production endpoint or credential is missing.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse


REGULAR_WHEEL_QR_PAYLOAD = "https://t.me/vnvncbattlebot?start=wheel"
TAILSCALE_IPV4_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def is_safe_kiosk_api_url(base_url: str) -> bool:
    """Allow HTTPS, loopback HTTP, or HTTP to a literal Tailscale IPv4 address.

    Tailscale encrypts the CGNAT hop and the kiosk signs every request with a
    device HMAC.  Requiring a literal 100.64.0.0/10 address prevents a public
    hostname or ordinary LAN endpoint from silently downgrading to HTTP.
    """

    parsed = urlparse(base_url)
    if not parsed.hostname:
        return False
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http":
        return False
    if parsed.hostname in {"127.0.0.1", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(parsed.hostname) in TAILSCALE_IPV4_NETWORK
    except ValueError:
        return False


class KioskClientError(RuntimeError):
    """A safe, user-presentable kiosk API failure."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class KioskConfigurationError(KioskClientError):
    """The production client is not safely configured."""

    def __init__(self, message: str) -> None:
        super().__init__("CONFIGURATION_ERROR", message, retryable=False)


@dataclass(frozen=True)
class SpinAllowance:
    """Backend-issued spin allowance, clamped to the kiosk's 1 + 2 contract."""

    base: int = 1
    bonus: int = 0
    total: int = 1
    used: int = 0
    left: int = 1
    active_boosts: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "SpinAllowance":
        payload = payload or {}
        base = 1 if int(payload.get("base", 1) or 0) > 0 else 0
        active_boosts = max(0, int(payload.get("active_boosts", 0) or 0))
        bonus = max(0, min(2, int(payload.get("bonus", active_boosts) or 0)))
        total = max(base, min(3, int(payload.get("total", base + bonus) or 0)))
        used = max(0, min(total, int(payload.get("used", 0) or 0)))
        left = max(0, min(total - used, int(payload.get("left", total - used) or 0)))
        return cls(
            base=base,
            bonus=bonus,
            total=total,
            used=used,
            left=left,
            active_boosts=active_boosts,
        )


@dataclass(frozen=True)
class KioskUser:
    telegram_id: int
    display_name: str
    username: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "KioskUser | None":
        if not payload:
            return None
        raw_id = payload.get("telegram_id", payload.get("id"))
        if raw_id is None:
            return None
        name = str(
            payload.get("display_name")
            or payload.get("first_name")
            or payload.get("username")
            or "ГОСТЬ"
        )
        username = payload.get("username")
        return cls(int(raw_id), name[:64], str(username) if username else None)


@dataclass(frozen=True)
class KioskSession:
    id: str
    status: str
    auth_mode: str
    club_night: str | None
    authenticated: bool
    user: KioskUser | None
    allowance: SpinAllowance

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "KioskSession":
        return cls(
            id=str(payload.get("id", "")),
            status=str(payload.get("status", "UNKNOWN")).upper(),
            auth_mode=str(payload.get("auth_mode", "telegram")).lower(),
            club_night=(str(payload["club_night"]) if payload.get("club_night") else None),
            authenticated=bool(payload.get("authenticated", False)),
            user=KioskUser.from_mapping(payload.get("user")),
            allowance=SpinAllowance.from_mapping(payload.get("allowance")),
        )


@dataclass(frozen=True)
class KioskAuth:
    pairing_id: str
    auth_url: str
    expires_at: str | None = None


@dataclass(frozen=True)
class KioskPrize:
    id: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class KioskCoupon:
    code: str
    expires_at: str | None
    redeem_qr_payload: str
    validity_slots: tuple[Mapping[str, Any], ...] = ()
    redemption_method: str = "staff_qr"
    show_prize_qr: bool = True
    redeemable_via_staff: bool = True
    text_promo_code: str | None = None


@dataclass(frozen=True)
class KioskAward:
    id: str
    prize: KioskPrize
    coupon: KioskCoupon
    source_credit: str | None = None
    issued_at: str | None = None
    test_mode: bool = False


@dataclass(frozen=True)
class KioskSpinResult:
    award: KioskAward
    session: KioskSession
    idempotent: bool = False


class KioskClient(Protocol):
    async def create_session(self, *, request_id: str, auth_mode: str) -> KioskSession: ...

    async def get_session(self, session_id: str) -> KioskSession: ...

    async def start_auth(self, session_id: str) -> KioskAuth: ...

    async def spin(self, session_id: str, *, request_id: str) -> KioskSpinResult: ...

    async def finish_session(self, session_id: str) -> None: ...


class VNVNCKioskClient:
    """Small aiohttp client implementing the production kiosk API contract."""

    def __init__(
        self,
        *,
        base_url: str,
        device_id: str,
        device_secret: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not is_safe_kiosk_api_url(base_url):
            raise KioskConfigurationError(
                "Kiosk API must use HTTPS or a literal Tailscale IPv4 address"
            )
        if not device_id.strip() or not device_secret.strip():
            raise KioskConfigurationError("Kiosk device credential is missing")
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id.strip()
        self._device_secret = device_secret.encode("utf-8")
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def _signed_headers(self, method: str, path: str, raw_body: bytes) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        body_hash = hashlib.sha256(raw_body).hexdigest()
        canonical = "\n".join((method.upper(), path, timestamp, nonce, body_hash)).encode("utf-8")
        signature = hmac.new(self._device_secret, canonical, hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Artifact-Device-ID": self.device_id,
            "X-Artifact-Timestamp": timestamp,
            "X-Artifact-Nonce": nonce,
            "X-Artifact-Signature": signature,
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        import aiohttp

        raw_body = json.dumps(
            dict(payload or {}),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        headers = self._signed_headers(method, path, raw_body)
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            # The cabinet keeps legacy proxy variables for Gemini traffic.
            # Prize issuance must use the router/Tailscale route directly: an
            # ambient HTTP proxy can drop HMAC requests or see their headers.
            async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
                async with session.request(
                    method.upper(),
                    f"{self.base_url}{path}",
                    data=raw_body,
                    headers=headers,
                ) as response:
                    try:
                        data = await response.json(content_type=None)
                    except Exception as exc:
                        raise KioskClientError(
                            "BAD_RESPONSE", "СЕРВЕР ВЕРНУЛ НЕВЕРНЫЙ ОТВЕТ"
                        ) from exc
                    if response.status >= 400 or not data.get("success", False):
                        code = str(data.get("error") or data.get("code") or "SERVER_ERROR")
                        message = str(data.get("message") or "СЕРВЕР НЕ ВЫДАЛ ПРИЗ")
                        retryable = response.status >= 500 or code in {
                            "AUTH_PENDING",
                            "TEMPORARY_ERROR",
                            "TIMEOUT",
                        }
                        raise KioskClientError(code, message, retryable=retryable)
                    return data
        except KioskClientError:
            raise
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise KioskClientError("NETWORK_ERROR", "СВЯЗИ НЕТ · ПРИЗ НЕ РАЗЫГРАН") from exc

    async def create_session(self, *, request_id: str, auth_mode: str) -> KioskSession:
        auth_mode = _validate_auth_mode(auth_mode)
        data = await self._request(
            "POST",
            "/api/artifact-kiosk/session",
            {"request_id": request_id, "auth_mode": auth_mode},
        )
        return KioskSession.from_mapping(_require_mapping(data, "session"))

    async def get_session(self, session_id: str) -> KioskSession:
        path = f"/api/artifact-kiosk/session/{_safe_path_id(session_id)}"
        data = await self._request("GET", path)
        return KioskSession.from_mapping(_require_mapping(data, "session"))

    async def start_auth(self, session_id: str) -> KioskAuth:
        path = f"/api/artifact-kiosk/session/{_safe_path_id(session_id)}/auth/start"
        data = await self._request("POST", path)
        return KioskAuth(
            pairing_id=str(data.get("pairing_id", "")),
            auth_url=str(data.get("auth_url", "")),
            expires_at=(str(data["expires_at"]) if data.get("expires_at") else None),
        )

    async def spin(self, session_id: str, *, request_id: str) -> KioskSpinResult:
        path = f"/api/artifact-kiosk/session/{_safe_path_id(session_id)}/spin"
        data = await self._request("POST", path, {"request_id": request_id})
        return parse_spin_response(data)

    async def finish_session(self, session_id: str) -> None:
        path = f"/api/artifact-kiosk/session/{_safe_path_id(session_id)}/finish"
        await self._request("POST", path)


@dataclass
class _StubSession:
    id: str
    auth_mode: str
    active_boosts: int
    authenticated: bool = False
    polls: int = 0
    used: int = 0
    awards_by_request: dict[str, KioskSpinResult] = field(default_factory=dict)


class LocalKioskStub:
    """Deterministic simulator backend; never selected in hardware mode."""

    # Deposits remain on the presentation reel, but the simulator mirrors the
    # live issuance contract and never awards them.  Keeping that distinction
    # here prevents a QA spin from suggesting that a visual sector is live.
    PRIZES = (
        KioskPrize("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ", "Один коктейль"),
        KioskPrize("MERCHFREE", "БЕСПЛАТНЫЙ МЕРЧ", "Одна позиция мерча"),
        KioskPrize("SHOT1FREE", "БЕСПЛАТНЫЙ ШОТ", "Один шот"),
        KioskPrize("SHOTFR", "СЕТ ШОТОВ", "Один сет"),
        KioskPrize("TIX1FREE", "БИЛЕТ НА ОДНОГО", "Один проход"),
        KioskPrize(
            "TIX50",
            "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            "Текстовый промокод на скидку 50% на один билет",
        ),
    )

    def __init__(
        self,
        *,
        active_boosts: int = 0,
        auto_auth_after_polls: int | None = 2,
        online: bool = True,
    ) -> None:
        self.active_boosts = max(0, min(2, int(active_boosts)))
        self.auto_auth_after_polls = auto_auth_after_polls
        self.online = online
        self._sessions: dict[str, _StubSession] = {}
        self._award_index = 0

    def _ensure_online(self) -> None:
        if not self.online:
            raise KioskClientError("NETWORK_ERROR", "СВЯЗИ НЕТ · ПРИЗ НЕ РАЗЫГРАН")

    def _snapshot(self, session: _StubSession) -> KioskSession:
        paired = session.auth_mode == "telegram" and session.authenticated
        bonus = min(session.active_boosts, 2) if paired else 0
        total = 1 + bonus
        return KioskSession(
            id=session.id,
            status="READY" if session.auth_mode == "guest" or paired else "AUTH_PENDING",
            auth_mode=session.auth_mode,
            club_night="SIMULATOR",
            authenticated=paired,
            user=(KioskUser(424242, "ТЕСТОВЫЙ ГОСТЬ", "artifact_test") if paired else None),
            allowance=SpinAllowance(
                base=1,
                bonus=bonus,
                total=total,
                used=session.used,
                left=max(0, total - session.used),
                active_boosts=session.active_boosts if paired else 0,
            ),
        )

    async def create_session(self, *, request_id: str, auth_mode: str) -> KioskSession:
        self._ensure_online()
        auth_mode = _validate_auth_mode(auth_mode)
        session_id = f"stub-{request_id[:24]}"
        session = self._sessions.get(session_id)
        if session is None:
            session = _StubSession(session_id, auth_mode, self.active_boosts)
            self._sessions[session_id] = session
        return self._snapshot(session)

    async def get_session(self, session_id: str) -> KioskSession:
        self._ensure_online()
        session = self._sessions[session_id]
        session.polls += 1
        if (
            session.auth_mode == "telegram"
            and self.auto_auth_after_polls is not None
            and session.polls >= self.auto_auth_after_polls
        ):
            session.authenticated = True
        return self._snapshot(session)

    async def start_auth(self, session_id: str) -> KioskAuth:
        self._ensure_online()
        if session_id not in self._sessions:
            raise KioskClientError("NOT_FOUND", "СЕССИЯ НЕ НАЙДЕНА", retryable=False)
        # Mirror the production short-pairing contract so the simulator also
        # exercises a QR with at least two physical pixels per EC-H module.
        token = secrets.token_urlsafe(16)
        return KioskAuth(
            pairing_id=f"stub-pair-{token}",
            auth_url=f"https://example.test/k/{token}",
            expires_at=None,
        )

    async def spin(self, session_id: str, *, request_id: str) -> KioskSpinResult:
        self._ensure_online()
        session = self._sessions[session_id]
        if request_id in session.awards_by_request:
            previous = session.awards_by_request[request_id]
            return KioskSpinResult(previous.award, self._snapshot(session), idempotent=True)
        snapshot = self._snapshot(session)
        if snapshot.status != "READY":
            raise KioskClientError("AUTH_PENDING", "СНАЧАЛА ВОЙДИ ЧЕРЕЗ TELEGRAM")
        if snapshot.allowance.left <= 0:
            raise KioskClientError("NO_SPINS_LEFT", "СПИНЫ ЗАКОНЧИЛИСЬ", retryable=False)
        prize = self.PRIZES[self._award_index % len(self.PRIZES)]
        self._award_index += 1
        session.used += 1
        is_ticket_discount = prize.id == "TIX50"
        code = (
            f"260826-{self._award_index:010d}-50"
            if is_ticket_discount
            else f"VNVNC-K-STUB-{self._award_index:04d}"
        )
        award = KioskAward(
            id=f"stub-issue-{self._award_index:04d}",
            prize=prize,
            coupon=KioskCoupon(
                code=code,
                expires_at="2026-08-27T07:00:00+03:00",
                redeem_qr_payload=code,
                redemption_method="text_code" if is_ticket_discount else "staff_qr",
                show_prize_qr=not is_ticket_discount,
                redeemable_via_staff=not is_ticket_discount,
                text_promo_code=code if is_ticket_discount else None,
            ),
            source_credit="SIMULATOR",
            issued_at="2026-08-26T23:30:00+03:00",
        )
        result = KioskSpinResult(award, self._snapshot(session))
        session.awards_by_request[request_id] = result
        return result

    async def finish_session(self, session_id: str) -> None:
        self._ensure_online()
        self._sessions.pop(session_id, None)


def create_kiosk_client(*, environment: str | None = None) -> KioskClient:
    """Create the correct client without allowing a silent hardware stub."""

    env = (environment or os.getenv("ARTIFACT_ENV", "simulator")).strip().lower()
    use_stub = os.getenv("ARTIFACT_KIOSK_STUB", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if env != "hardware" and os.getenv("ARTIFACT_KIOSK_STUB", "").strip() == "":
        use_stub = True
    if use_stub:
        if env == "hardware":
            raise KioskConfigurationError("Local kiosk stub is forbidden in hardware mode")
        return LocalKioskStub(
            active_boosts=int(os.getenv("ARTIFACT_KIOSK_STUB_BOOSTS", "0") or 0),
            auto_auth_after_polls=int(os.getenv("ARTIFACT_KIOSK_STUB_AUTH_POLLS", "2") or 2),
        )
    return VNVNCKioskClient(
        base_url=os.getenv("VNVNC_KIOSK_API_BASE_URL", "https://api.vnvnc.ru"),
        device_id=os.getenv("ARTIFACT_KIOSK_DEVICE_ID", ""),
        device_secret=os.getenv("ARTIFACT_KIOSK_DEVICE_SECRET", ""),
        timeout_seconds=float(os.getenv("ARTIFACT_KIOSK_TIMEOUT_SECONDS", "8") or 8),
    )


def _validate_auth_mode(auth_mode: str) -> str:
    normalized = str(auth_mode).strip().lower()
    if normalized not in {"telegram", "guest"}:
        raise ValueError(f"Unsupported auth mode: {auth_mode!r}")
    return normalized


def _safe_path_id(value: str) -> str:
    value = str(value).strip()
    safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if not value or any(char not in safe_chars for char in value):
        raise ValueError("Unsafe kiosk session id")
    return value


def _require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise KioskClientError("BAD_RESPONSE", f"СЕРВЕР НЕ ВЕРНУЛ {key.upper()}")
    return value


def parse_spin_response(data: Mapping[str, Any]) -> KioskSpinResult:
    """Parse both the current flat award and the earlier nested wire shape."""

    award_payload = _require_mapping(data, "award")
    nested_prize = award_payload.get("prize")
    prize_payload = nested_prize if isinstance(nested_prize, Mapping) else award_payload
    nested_coupon = award_payload.get("coupon")
    coupon_payload = nested_coupon if isinstance(nested_coupon, Mapping) else award_payload
    prize_id = str(prize_payload.get("id") or prize_payload.get("prize_id") or "").strip()

    def coupon_value(key: str) -> Any:
        return coupon_payload[key] if key in coupon_payload else award_payload.get(key)

    raw_code = str(
        coupon_value("code") or coupon_value("coupon_code") or ""
    ).strip()
    code = raw_code.upper()
    redeem_payload = str(coupon_value("redeem_qr_payload") or "").strip()
    if not code or raw_code != code:
        raise KioskClientError("BAD_RESPONSE", "СЕРВЕР НЕ ВЕРНУЛ КОД ПРИЗА")

    is_ticket_discount = prize_id == "TIX50"
    if is_ticket_discount:
        text_promo_code = str(coupon_value("text_promo_code") or "").strip()
        redemption_method = str(coupon_value("redemption_method") or "").strip()
        if (
            redeem_payload
            or text_promo_code != code
            or redemption_method != "text_code"
            or coupon_value("show_prize_qr") is not False
            or coupon_value("redeemable_via_staff") is not False
        ):
            raise KioskClientError(
                "BAD_RESPONSE",
                "ТЕКСТОВЫЙ КОД БИЛЕТА НЕ СОВПАДАЕТ С КОНТРАКТОМ",
            )
        # Internally retain the code as a compatibility payload for printing;
        # PrizeDrumMode branches on TIX50 and never turns it into a QR.
        normalized_redeem_payload = code
    else:
        text_promo_code = None
        redemption_method = str(
            coupon_value("redemption_method")
            or "staff_qr"
        ).strip()
        if not redeem_payload:
            raise KioskClientError("BAD_RESPONSE", "СЕРВЕР НЕ ВЕРНУЛ QR ПРИЗА")
        if redeem_payload != code:
            raise KioskClientError("BAD_RESPONSE", "QR ПРИЗА НЕ СОВПАДАЕТ С КОДОМ")
        normalized_redeem_payload = redeem_payload
    slots = coupon_payload.get("validity_slots") or ()
    award = KioskAward(
        id=str(award_payload.get("id") or award_payload.get("issue_id") or ""),
        prize=KioskPrize(
            id=prize_id,
            label=str(
                prize_payload.get("label")
                or prize_payload.get("prize_label")
                or prize_payload.get("prize_title")
                or "ПРИЗ"
            ),
            description=str(
                prize_payload.get("description")
                or prize_payload.get("prize_description")
                or prize_payload.get("terms")
                or ""
            ),
        ),
        coupon=KioskCoupon(
            code=code,
            expires_at=(
                str(coupon_payload["expires_at"])
                if coupon_payload.get("expires_at")
                else None
            ),
            redeem_qr_payload=normalized_redeem_payload,
            validity_slots=tuple(slot for slot in slots if isinstance(slot, Mapping)),
            redemption_method=redemption_method,
            show_prize_qr=not is_ticket_discount,
            redeemable_via_staff=not is_ticket_discount,
            text_promo_code=text_promo_code,
        ),
        source_credit=(
            str(award_payload["source_credit"])
            if award_payload.get("source_credit")
            else None
        ),
        issued_at=(str(award_payload["issued_at"]) if award_payload.get("issued_at") else None),
        test_mode=bool(award_payload.get("test_mode", False)),
    )
    if not award.id or not award.prize.id:
        raise KioskClientError("BAD_RESPONSE", "СЕРВЕР НЕ ВЕРНУЛ ИДЕНТИФИКАТОР ПРИЗА")
    return KioskSpinResult(
        award=award,
        session=KioskSession.from_mapping(_require_mapping(data, "session")),
        idempotent=bool(data.get("idempotent", False)),
    )
