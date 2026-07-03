"""Russian admin Telegram bot for the VNVNC arcade machine."""

from __future__ import annotations

import asyncio
import html
import io
import json
import logging
import os
import re
import subprocess
import time
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from aiohttp import web
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from artifact.modes.photobooth import get_configured_photobooth_modes
from artifact.telegram.events import EVENT_LOG, read_bot_events


logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DATA_DIR = Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))
CONTROL_FILE = Path(os.environ.get("ARCADE_CONTROL_FILE", str(DATA_DIR / "control.json")))
STATUS_FILE = Path(os.environ.get("ARCADE_STATUS_FILE", str(DATA_DIR / "status.json")))
CONTROL_RESPONSE_DIR = Path(os.environ.get("ARCADE_CONTROL_RESPONSE_DIR", str(DATA_DIR / "control_responses")))
AI_LOG_DIR = Path(os.environ.get("VNVNC_AI_LOG_DIR", "/home/kirniy/modular-arcade/vnvnc_ai_logs"))
UPLOAD_SPOOL_DIR = Path(os.environ.get("ARCADE_UPLOAD_SPOOL_DIR", "/home/kirniy/modular-arcade/data/upload_spool"))


def _parse_ids(value: str, default: set[int]) -> set[int]:
    ids: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError:
            logger.warning("Ignoring invalid Telegram id: %s", item)
    return ids or default


ADMIN_IDS = _parse_ids(os.environ.get("ARCADE_ADMIN_IDS", "433491"), {433491})
TRIAL_CREDIT_USD = float(os.environ.get("ARCADE_TRIAL_CREDIT_USD", "300"))
IMAGE_CALL_COST_USD = float(os.environ.get("ARCADE_GEMINI_IMAGE_COST_USD", "0.04"))
TEXT_CALL_COST_USD = float(os.environ.get("ARCADE_GEMINI_TEXT_COST_USD", "0.002"))


def _now() -> datetime:
    return datetime.now(MOSCOW_TZ)


def _format_dt(ts: float | str | None) -> str:
    if ts is None:
        return "нет данных"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(float(ts), MOSCOW_TZ)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=MOSCOW_TZ)
            else:
                dt = dt.astimezone(MOSCOW_TZ)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return str(ts)


def _event_dt(event: dict[str, Any]) -> datetime:
    ts = event.get("timestamp")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), MOSCOW_TZ)
    if isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return parsed.astimezone(MOSCOW_TZ) if parsed.tzinfo else parsed.replace(tzinfo=MOSCOW_TZ)
        except ValueError:
            pass
    return _now()


def _club_night_window(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    current = now or _now()
    if current.hour < 7:
        start_date = current.date() - timedelta(days=1)
        end_date = current.date()
    elif current.hour >= 23:
        start_date = current.date()
        end_date = current.date() + timedelta(days=1)
    else:
        start_date = current.date() - timedelta(days=1)
        end_date = current.date()
    return (
        datetime.combine(start_date, datetime.min.time(), MOSCOW_TZ).replace(hour=23),
        datetime.combine(end_date, datetime.min.time(), MOSCOW_TZ).replace(hour=7),
    )


def _report_window_for_day(day: datetime) -> tuple[datetime, datetime]:
    end = datetime.combine(day.date(), datetime.min.time(), MOSCOW_TZ).replace(hour=7)
    return end - timedelta(hours=8), end


@dataclass
class Coupon:
    code: str
    prize_type: str
    prize_label: str
    source: str
    created_at: str
    expires_at: str
    is_redeemed: bool = False
    redeemed_at: Optional[str] = None
    redeemed_by: Optional[int] = None


class CouponStore:
    """Compatibility store for older arcade modes that still issue coupons."""

    PRIZE_LABELS = {
        "COCKTL": "Бесплатный коктейль",
        "SHOTFR": "Бесплатный шот",
        "DEP5K": "Депозит 5000₽",
        "DEP10K": "Депозит 10000₽",
        "MERCHX": "Мерч VNVNC",
    }

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "coupons.json"
        self._coupons: dict[str, Coupon] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._coupons = {code: Coupon(**data) for code, data in payload.items()}
        except Exception as e:
            logger.warning("Could not load coupons: %s", e)

    def _save(self) -> None:
        self.path.write_text(
            json.dumps({code: asdict(coupon) for code, coupon in self._coupons.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_coupon(self, code: str, prize_type: str, source: str) -> Coupon:
        now = _now()
        coupon = Coupon(
            code=code.upper(),
            prize_type=prize_type,
            prize_label=self.PRIZE_LABELS.get(prize_type, prize_type),
            source=source,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        )
        self._coupons[coupon.code] = coupon
        self._save()
        return coupon

    def get_recent(self, limit: int = 10) -> list[Coupon]:
        return sorted(self._coupons.values(), key=lambda item: item.created_at, reverse=True)[:limit]


class ArcadeControl:
    """File-based control channel read by the root hardware runner."""

    def __init__(self, control_file: Path = CONTROL_FILE) -> None:
        self.control_file = control_file
        self.control_file.parent.mkdir(parents=True, exist_ok=True)
        CONTROL_RESPONSE_DIR.mkdir(parents=True, exist_ok=True)

    def write_command(self, command: str, **kwargs: Any) -> str:
        command_id = uuid.uuid4().hex
        payload = {
            "command_id": command_id,
            "command": command,
            "timestamp": time.time(),
            "timestamp_iso": _now().isoformat(),
            **kwargs,
        }
        self.control_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            self.control_file.chmod(0o666)
        except OSError:
            pass
        logger.info("Wrote control command %s (%s)", command, command_id)
        return command_id

    async def wait_response(self, command_id: str, timeout: float = 10.0) -> Optional[dict[str, Any]]:
        path = CONTROL_RESPONSE_DIR / f"{command_id}.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    path.unlink(missing_ok=True)
                    return payload
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            await asyncio.sleep(0.2)
        return None

    def status(self) -> dict[str, Any]:
        if not STATUS_FILE.exists():
            return {}
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def button(self, button: str) -> None:
        self.write_command("button", button=button)

    def mode(self, mode: str) -> None:
        self.write_command("start_mode", mode=mode)

    def idle_next(self) -> None:
        self.write_command("idle_next")

    def idle_prev(self) -> None:
        self.write_command("idle_prev")

    def mute(self) -> None:
        self.write_command("mute")

    def unmute(self) -> None:
        self.write_command("unmute")

    def machine_reboot(self) -> str:
        return self.write_command("system_reboot")

    async def capture_photo(self) -> Optional[dict[str, Any]]:
        command_id = self.write_command("capture_photo")
        return await self.wait_response(command_id, timeout=12.0)


class StatsReader:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir

    def events(self) -> list[dict[str, Any]]:
        return list(read_bot_events(EVENT_LOG) or [])

    def photo_events(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[dict[str, Any]]:
        photos: list[dict[str, Any]] = []
        for event in self.events():
            if event.get("type") != "photobooth_photo":
                continue
            dt = _event_dt(event)
            if start and dt < start:
                continue
            if end and dt >= end:
                continue
            photos.append(event)
        return photos

    def _count_ai_logs(self, start: Optional[datetime], end: Optional[datetime]) -> tuple[int, int]:
        image_count = 0
        text_count = 0
        if not AI_LOG_DIR.exists():
            return image_count, text_count

        for meta_path in AI_LOG_DIR.glob("*/metadata/*_meta.json"):
            if self._log_in_window(meta_path, start, end):
                image_count += 1
        for text_path in AI_LOG_DIR.glob("*/text/*.json"):
            if self._log_in_window(text_path, start, end):
                text_count += 1
        return image_count, text_count

    @staticmethod
    def _log_in_window(path: Path, start: Optional[datetime], end: Optional[datetime]) -> bool:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            value = payload.get("timestamp")
            if not value:
                return False
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            dt = dt.astimezone(MOSCOW_TZ) if dt.tzinfo else dt.replace(tzinfo=MOSCOW_TZ)
            return (start is None or dt >= start) and (end is None or dt < end)
        except Exception:
            return False

    def pending_uploads(self) -> int:
        if not UPLOAD_SPOOL_DIR.exists():
            return 0
        return len(list(UPLOAD_SPOOL_DIR.glob("*/*.json")))

    def build_stats(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> dict[str, Any]:
        photos = self.photo_events(start, end)
        photo_groups: dict[str, list[dict[str, Any]]] = {}
        for event in photos:
            photo_groups.setdefault(self._photo_key(event), []).append(event)

        final_photos = [self._final_photo_event(events) for events in photo_groups.values()]
        successful = [event for event in final_photos if event.get("success")]
        failed = [
            event
            for event in final_photos
            if not event.get("success") and not event.get("skipped") and not self._is_retryable_upload_failure(event)
        ]
        image_calls, text_calls = self._count_ai_logs(start, end)
        spent = image_calls * IMAGE_CALL_COST_USD + text_calls * TEXT_CALL_COST_USD
        return {
            "photos": len(final_photos),
            "successful_photos": len(successful),
            "failed_photos": len(failed),
            "image_calls": image_calls,
            "text_calls": text_calls,
            "spent": spent,
            "trial_left": max(0.0, TRIAL_CREDIT_USD - spent),
            "pending_uploads": self.pending_uploads(),
            "last_photo": successful[-1] if successful else None,
        }

    @staticmethod
    def _photo_key(event: dict[str, Any]) -> str:
        for field in ("short_id", "filename"):
            value = event.get(field)
            if value:
                return str(value)
        for field in ("url", "error"):
            value = str(event.get(field) or "")
            match = re.search(r"(photobooth_\d{8}_\d{6}_[a-f0-9]+\.png)", value)
            if match:
                return match.group(1)
        return str(event.get("id") or event.get("timestamp") or uuid.uuid4().hex)

    @staticmethod
    def _final_photo_event(events: list[dict[str, Any]]) -> dict[str, Any]:
        successful = [event for event in events if event.get("success")]
        if successful:
            return successful[-1]
        return events[-1]

    @staticmethod
    def _is_retryable_upload_failure(event: dict[str, Any]) -> bool:
        error = str(event.get("error") or "")
        retryable_markers = (
            "SSLEOFError",
            "UNEXPECTED_EOF_WHILE_READING",
            "Max retries exceeded",
            "s3.ru-7.storage.selcloud.ru",
        )
        return any(marker in error for marker in retryable_markers)


class ArcadeBot:
    def __init__(self, token: Optional[str] = None, data_dir: Path = DATA_DIR) -> None:
        self.token = token if token is not None else os.environ.get("ARCADE_BOT_TOKEN", "").strip()
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "bot_state.json"
        self.coupons = CouponStore(data_dir)
        self.control = ArcadeControl()
        self.stats = StatsReader(data_dir)
        self.app: Optional[Application] = None
        self._running = False
        self._event_task: Optional[asyncio.Task] = None
        self._report_task: Optional[asyncio.Task] = None
        self._state = self._load_state()

    @classmethod
    def get_available_mode_buttons(cls) -> list[dict[str, str]]:
        buttons: list[dict[str, str]] = []
        for mode_cls in get_configured_photobooth_modes():
            buttons.append(
                {
                    "name": mode_cls.name,
                    "icon": getattr(mode_cls, "icon", "📸"),
                    "label": getattr(mode_cls, "display_name", mode_cls.name).strip(),
                }
            )
        return buttons

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"event_offset": 0, "last_report_date": ""}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"event_offset": 0, "last_report_date": ""}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _existing_file_path(value: Any) -> Optional[Path]:
        if not value:
            return None
        try:
            path = Path(str(value))
            return path if path.is_file() else None
        except OSError:
            return None

    @staticmethod
    def _event_photo_key(event: dict[str, Any]) -> str:
        return StatsReader._photo_key(event)

    def _sent_photo_keys(self) -> list[str]:
        keys = self._state.setdefault("sent_photo_keys", [])
        if not isinstance(keys, list):
            keys = []
            self._state["sent_photo_keys"] = keys
        return [str(key) for key in keys if key]

    def _mark_photo_sent(self, key: str) -> None:
        keys = self._sent_photo_keys()
        if key in keys:
            keys.remove(key)
        keys.append(key)
        self._state["sent_photo_keys"] = keys[-500:]
        self._save_state()

    def is_admin(self, user_id: int) -> bool:
        return user_id in ADMIN_IDS

    async def start(self) -> None:
        if not self.token:
            raise RuntimeError("ARCADE_BOT_TOKEN is not set")

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("photo", self._cmd_photo))
        self.app.add_handler(CommandHandler("reboot", self._cmd_reboot))
        self.app.add_handler(CommandHandler("control", self._cmd_control))
        self.app.add_handler(CommandHandler("mode", self._cmd_mode))
        self.app.add_handler(CommandHandler("button", self._cmd_button))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        self.app.add_handler(CommandHandler("coupons", self._cmd_coupons))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        await self.app.initialize()
        try:
            await self.app.bot.set_my_commands(
                [
                    BotCommand("start", "Главное меню"),
                    BotCommand("status", "Статус автомата"),
                    BotCommand("stats", "Статистика сейчас"),
                    BotCommand("report", "Отчет за клубную ночь"),
                    BotCommand("photo", "Сделать фото с камеры"),
                    BotCommand("control", "Пульт управления"),
                    BotCommand("mode", "Запустить режим"),
                    BotCommand("reboot", "Перезагрузить машину"),
                    BotCommand("logs", "Последние логи"),
                ]
            )
        except Exception as e:
            logger.warning("Could not set Telegram command menu: %s", e)
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        self._running = True
        self._event_task = asyncio.create_task(self._event_loop())
        self._report_task = asyncio.create_task(self._daily_report_loop())
        await self.notify_admins("Бот VNVNC запущен. Я на связи.")
        logger.info("VNVNC admin bot started")

    async def stop(self) -> None:
        for task in (self._event_task, self._report_task):
            if task:
                task.cancel()
        if self.app:
            try:
                if self._running and self.app.updater:
                    await self.app.updater.stop()
            except Exception:
                logger.debug("Bot updater stop failed", exc_info=True)
            try:
                if self._running:
                    await self.app.stop()
            except Exception:
                logger.debug("Bot application stop failed", exc_info=True)
            try:
                await self.app.shutdown()
            except Exception:
                logger.debug("Bot application shutdown failed", exc_info=True)
        self._running = False

    async def notify_admins(self, message: str, **kwargs: Any) -> None:
        if not self.app:
            return
        for admin_id in ADMIN_IDS:
            try:
                await self.app.bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML", **kwargs)
            except Exception as e:
                logger.warning("Could not notify admin %s: %s", admin_id, e)

    async def _admin_only(self, update: Update) -> bool:
        user = update.effective_user
        if user and self.is_admin(user.id):
            return True
        if update.effective_message:
            await update.effective_message.reply_text("Доступ закрыт.")
        return False

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(self._main_text(), parse_mode="HTML", reply_markup=self._main_keyboard())

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(
            "Команды:\n"
            "/status — состояние автомата\n"
            "/stats — сводка и деньги\n"
            "/report — отчет за последнюю клубную ночь 23:00-07:00\n"
            "/photo — сделать фото с камеры автомата\n"
            "/control — кнопки управления\n"
            "/mode — список режимов, /mode <name> — запуск\n"
            "/reboot — перезагрузка Raspberry Pi\n"
            "/logs — последние логи",
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(self._format_status(), parse_mode="HTML")

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        start, end = _club_night_window()
        await update.message.reply_text(self._format_stats(start, end, "Текущая/последняя клубная ночь"), parse_mode="HTML")

    async def _cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        start, end = _report_window_for_day(_now())
        await update.message.reply_text(self._format_stats(start, end, "Отчет 23:00-07:00"), parse_mode="HTML")

    async def _cmd_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        msg = await update.message.reply_text("Делаю фото с камеры автомата...")
        response = await self.control.capture_photo()
        if not response:
            await msg.edit_text("Камера не ответила за 12 секунд.")
            return
        if not response.get("ok"):
            await msg.edit_text(f"Не удалось сделать фото: {html.escape(str(response.get('error', 'ошибка')))}")
            return
        path = Path(str(response.get("path", "")))
        if not path.exists():
            await msg.edit_text("Фото сделано, но файл не найден.")
            return
        await msg.delete()
        with path.open("rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=f"Фото с камеры автомата\nРазмер: {response.get('bytes', '?')} байт\nВремя: {_format_dt(response.get('timestamp'))}",
            )

    async def _cmd_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(
            "Перезагрузить всю машину?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Да, перезагрузить", callback_data="reboot:confirm")]]
            ),
        )

    async def _cmd_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(self._format_status(), parse_mode="HTML", reply_markup=self._control_keyboard())

    async def _cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        modes = self.get_available_mode_buttons()
        if not context.args:
            await update.message.reply_text(
                "Режимы:\n" + "\n".join(f"{item['icon']} <code>{item['name']}</code> — {html.escape(item['label'])}" for item in modes),
                parse_mode="HTML",
            )
            return
        mode = context.args[0].strip()
        if mode not in {item["name"] for item in modes}:
            await update.message.reply_text("Такого режима нет. Список: /mode")
            return
        self.control.mode(mode)
        await update.message.reply_text(f"Запускаю режим <code>{html.escape(mode)}</code>", parse_mode="HTML")

    async def _cmd_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        if not context.args or context.args[0] not in {"start", "left", "right", "back", "up", "down"}:
            await update.message.reply_text("Кнопки: /button start|left|right|back|up|down")
            return
        self.control.button(context.args[0])
        await update.message.reply_text(f"Нажал: {context.args[0]}")

    async def _cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        text = await asyncio.to_thread(self._read_recent_logs)
        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_coupons(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        coupons = self.coupons.get_recent(10)
        if not coupons:
            await update.message.reply_text("Купонов нет.")
            return
        lines = ["Последние купоны:"]
        for coupon in coupons:
            status = "погашен" if coupon.is_redeemed else "активен"
            lines.append(f"<code>{html.escape(coupon.code)}</code> — {html.escape(coupon.prize_label)} — {status}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._admin_only(update):
            return
        await update.message.reply_text(self._main_text(), parse_mode="HTML", reply_markup=self._main_keyboard())

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("Доступ закрыт.")
            return

        data = query.data or ""
        if data == "main":
            await query.edit_message_text(self._main_text(), parse_mode="HTML", reply_markup=self._main_keyboard())
        elif data == "stats":
            start, end = _club_night_window()
            await query.edit_message_text(self._format_stats(start, end, "Текущая/последняя клубная ночь"), parse_mode="HTML", reply_markup=self._main_keyboard())
        elif data == "status":
            await query.edit_message_text(self._format_status(), parse_mode="HTML", reply_markup=self._control_keyboard())
        elif data == "photo":
            await query.edit_message_text("Делаю фото с камеры автомата...")
            response = await self.control.capture_photo()
            if response and response.get("ok") and Path(str(response.get("path", ""))).exists():
                path = Path(str(response["path"]))
                with path.open("rb") as f:
                    await query.message.reply_photo(photo=f, caption="Фото с камеры автомата")
                await query.message.reply_text(self._main_text(), parse_mode="HTML", reply_markup=self._main_keyboard())
            else:
                await query.message.reply_text(f"Фото не получилось: {response or 'нет ответа'}", reply_markup=self._main_keyboard())
        elif data == "reboot:confirm":
            self.control.machine_reboot()
            await query.edit_message_text("Команда перезагрузки отправлена. Машина сейчас уйдет в reboot.")
        elif data.startswith("ctrl:"):
            action = data.split(":", 1)[1]
            self._handle_control_action(action)
            await query.edit_message_text(self._format_status(), parse_mode="HTML", reply_markup=self._control_keyboard())

    def _handle_control_action(self, action: str) -> None:
        if action == "left":
            self.control.button("left")
        elif action == "start":
            self.control.button("start")
        elif action == "right":
            self.control.button("right")
        elif action == "back":
            self.control.button("back")
        elif action == "idle_prev":
            self.control.idle_prev()
        elif action == "idle_next":
            self.control.idle_next()
        elif action == "mute":
            self.control.mute()
        elif action == "unmute":
            self.control.unmute()

    def _main_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Статус", callback_data="status"), InlineKeyboardButton("Статистика", callback_data="stats")],
                [InlineKeyboardButton("Сделать фото", callback_data="photo")],
                [InlineKeyboardButton("Перезагрузка", callback_data="reboot:confirm")],
            ]
        )

    def _control_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Влево", callback_data="ctrl:left"),
                    InlineKeyboardButton("Старт", callback_data="ctrl:start"),
                    InlineKeyboardButton("Вправо", callback_data="ctrl:right"),
                ],
                [
                    InlineKeyboardButton("Сцена -", callback_data="ctrl:idle_prev"),
                    InlineKeyboardButton("Сцена +", callback_data="ctrl:idle_next"),
                ],
                [
                    InlineKeyboardButton("Звук выкл", callback_data="ctrl:mute"),
                    InlineKeyboardButton("Звук вкл", callback_data="ctrl:unmute"),
                ],
                [InlineKeyboardButton("Назад", callback_data="ctrl:back"), InlineKeyboardButton("Главное", callback_data="main")],
            ]
        )

    def _main_text(self) -> str:
        return (
            "<b>VNVNC ARCADE</b>\n"
            "Админ-бот автомата.\n\n"
            "Я присылаю каждое готовое фото, считаю ночную статистику и в 07:00 отправляю отчет за клубную ночь."
        )

    def _format_status(self) -> str:
        status = self.control.status()
        if not status:
            return "<b>Статус автомата</b>\nНет свежего status.json. Возможно, сервис artifact не запущен."
        ts = status.get("timestamp")
        age = int(time.time() - float(ts)) if isinstance(ts, (int, float)) else None
        return (
            "<b>Статус автомата</b>\n"
            f"Режим: <code>{html.escape(str(status.get('mode', '?')))}</code>\n"
            f"Сцена: <code>{html.escape(str(status.get('scene', status.get('idle_scene', '?'))))}</code>\n"
            f"Кадр: <code>{html.escape(str(status.get('frame', '?')))}</code>\n"
            f"Громкость: <code>{html.escape(str(status.get('volume', '?')))}</code>\n"
            f"Звук: {'выкл' if status.get('muted') else 'вкл'}\n"
            f"Работает: {'да' if status.get('running') else 'нет'}\n"
            f"Обновлено: {_format_dt(ts)}" + (f" ({age} сек назад)" if age is not None else "")
        )

    def _format_stats(self, start: datetime, end: datetime, title: str) -> str:
        stats = self.stats.build_stats(start, end)
        last_photo = stats["last_photo"]
        last_line = "нет"
        if last_photo:
            last_line = f"{_format_dt(last_photo.get('timestamp'))} — {html.escape(str(last_photo.get('short_url') or last_photo.get('url') or ''))}"
        return (
            f"<b>{html.escape(title)}</b>\n"
            f"Период: {start.strftime('%d.%m %H:%M')} - {end.strftime('%d.%m %H:%M')}\n\n"
            f"Фото всего: <b>{stats['photos']}</b>\n"
            f"Успешно загружено: <b>{stats['successful_photos']}</b>\n"
            f"Ошибки загрузки: <b>{stats['failed_photos']}</b>\n"
            f"Очередь Selectel: <b>{stats['pending_uploads']}</b>\n\n"
            f"AI image calls: <b>{stats['image_calls']}</b>\n"
            f"AI text calls: <b>{stats['text_calls']}</b>\n"
            f"Оценка расходов: <b>${stats['spent']:.2f}</b>\n"
            f"Оценка остатка trial $300: <b>${stats['trial_left']:.2f}</b>\n"
            "Это расчет по локальным логам, не официальный баланс Google/OpenRouter.\n\n"
            f"Последнее фото: {last_line}"
        )

    def _read_recent_logs(self) -> str:
        commands = [
            [
                "journalctl",
                "-u",
                "artifact",
                "-u",
                "arcade-bot",
                "-u",
                "artifact-upload-spool",
                "-n",
                "80",
                "--no-pager",
                "--output=short-iso",
            ],
            ["journalctl", "-n", "80", "--no-pager", "--output=short-iso"],
        ]
        for command in commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                output = (result.stdout or result.stderr or "").strip()
                if output:
                    escaped = html.escape(output[-3500:])
                    return f"<b>Последние логи</b>\n<pre>{escaped}</pre>"
            except Exception:
                logger.debug("Could not read logs with command: %s", command, exc_info=True)
        return "Логи не найдены. journalctl не отдал данные пользователю bot."

    async def _event_loop(self) -> None:
        while True:
            try:
                await self._send_new_events()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Bot event loop failed")
            await asyncio.sleep(5)

    async def _send_new_events(self) -> None:
        events = self.stats.events()
        offset = int(self._state.get("event_offset", 0))
        if offset > len(events):
            offset = 0
        for event in events[offset:]:
            delivered = await self._send_event(event)
            if not delivered:
                break
            offset += 1
            self._state["event_offset"] = offset
            self._save_state()

    async def _send_event(self, event: dict[str, Any]) -> bool:
        if event.get("type") != "photobooth_photo":
            return True
        if self._is_retryable_upload_failure(event):
            logger.info("Skipping retryable upload failure event %s", event.get("id"))
            return True
        photo_key = self._event_photo_key(event)
        if event.get("success") and photo_key in self._sent_photo_keys():
            logger.info("Skipping duplicate photo event %s for %s", event.get("id"), photo_key)
            return True
        caption = self._photo_caption(event)
        delivered = True
        for admin_id in ADMIN_IDS:
            try:
                if event.get("success") and event.get("url"):
                    await self._send_photo_with_fallback(admin_id, event, caption)
                elif event.get("skipped") and (source_path := self._existing_file_path(event.get("source_photo_path"))):
                    source_data = await asyncio.to_thread(source_path.read_bytes)
                    source_photo = io.BytesIO(source_data)
                    source_photo.name = source_path.name
                    await self.app.bot.send_photo(chat_id=admin_id, photo=source_photo, caption=caption)
                else:
                    await self.app.bot.send_message(chat_id=admin_id, text=caption)
            except Exception as e:
                delivered = False
                logger.warning("Failed to send event %s to %s: %s", event.get("id"), admin_id, e)
        if delivered and event.get("success"):
            self._mark_photo_sent(photo_key)
        return delivered

    async def _send_photo_with_fallback(self, admin_id: int, event: dict[str, Any], caption: str) -> None:
        source_photo_path = self._existing_file_path(event.get("source_photo_path"))
        if source_photo_path:
            await self._send_result_and_source_photo(admin_id, event, caption, source_photo_path)
            return

        await self._send_result_photo_only(admin_id, event, caption)

    async def _send_result_photo_only(self, admin_id: int, event: dict[str, Any], caption: str) -> None:
        url = str(event["url"])
        try:
            await self.app.bot.send_photo(chat_id=admin_id, photo=url, caption=caption)
            return
        except Exception as e:
            logger.warning("Telegram could not fetch photo URL directly; uploading bytes: %s", e)

        try:
            data = await asyncio.to_thread(self._download_photo_bytes, url)
            photo = io.BytesIO(data)
            photo.name = str(event.get("filename") or "photobooth.png")
            await self.app.bot.send_photo(chat_id=admin_id, photo=photo, caption=caption)
            return
        except Exception as e:
            logger.warning("Telegram byte photo upload failed; sending link only: %s", e)

        await self.app.bot.send_message(chat_id=admin_id, text=caption)

    async def _send_result_and_source_photo(
        self,
        admin_id: int,
        event: dict[str, Any],
        caption: str,
        source_photo_path: Path,
    ) -> None:
        url = str(event["url"])
        try:
            result_data = await asyncio.to_thread(self._download_photo_bytes, url)
            source_data = await asyncio.to_thread(source_photo_path.read_bytes)
            result_photo = io.BytesIO(result_data)
            result_photo.name = str(event.get("filename") or "photobooth.png")
            source_photo = io.BytesIO(source_data)
            source_photo.name = source_photo_path.name
            await self.app.bot.send_media_group(
                chat_id=admin_id,
                media=[
                    InputMediaPhoto(media=result_photo, caption=caption),
                    InputMediaPhoto(media=source_photo, caption="Исходное фото"),
                ],
            )
            return
        except Exception as e:
            logger.warning("Telegram media group upload failed; sending result only: %s", e)

        await self._send_result_photo_only(admin_id, event, caption)

    @staticmethod
    def _download_photo_bytes(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "VNVNC-Arcade-Bot/1.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read(20 * 1024 * 1024)

    @staticmethod
    def _is_retryable_upload_failure(event: dict[str, Any]) -> bool:
        if event.get("success"):
            return False
        error = str(event.get("error") or "")
        retryable_markers = (
            "SSLEOFError",
            "UNEXPECTED_EOF_WHILE_READING",
            "Max retries exceeded",
            "s3.ru-7.storage.selcloud.ru",
        )
        return any(marker in error for marker in retryable_markers)

    @staticmethod
    def _photo_caption(event: dict[str, Any]) -> str:
        if event.get("skipped"):
            return (
                "Фото не опубликовано в галерею\n"
                f"Время: {_format_dt(event.get('timestamp'))}\n"
                f"Тема: {event.get('theme_name') or event.get('theme_id') or 'unknown'}\n"
                f"Причина: {event.get('error') or 'нет видимого лица в исходном кадре'}\n"
                f"Размер результата: {event.get('result_bytes', 0)} байт\n"
                f"Размер исходника: {event.get('source_photo_bytes', 0)} байт"
            )
        if event.get("success"):
            return (
                "Новое фото готово\n"
                f"Время: {_format_dt(event.get('timestamp'))}\n"
                f"Тема: {event.get('theme_name') or event.get('theme_id') or 'unknown'}\n"
                f"Файл: {event.get('url') or ''}\n"
                f"Короткая ссылка: {event.get('short_url') or 'нет'}\n"
                f"Размер результата: {event.get('result_bytes', 0)} байт\n"
                f"Размер исходника: {event.get('source_photo_bytes', 0)} байт"
            )
        return (
            "Ошибка фото/загрузки\n"
            f"Время: {_format_dt(event.get('timestamp'))}\n"
            f"Тема: {event.get('theme_name') or event.get('theme_id') or 'unknown'}\n"
            f"Ошибка: {event.get('error') or 'unknown'}"
        )

    async def _daily_report_loop(self) -> None:
        while True:
            try:
                now = _now()
                today_key = now.strftime("%Y-%m-%d")
                if now.hour == 7 and now.minute < 10 and self._state.get("last_report_date") != today_key:
                    start, end = _report_window_for_day(now)
                    await self.notify_admins(self._format_stats(start, end, "Утренний отчет за клубную ночь"))
                    self._state["last_report_date"] = today_key
                    self._save_state()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Daily report loop failed")
            await asyncio.sleep(60)

    def create_coupon(self, code: str, prize_type: str, source: str = "ARCADE") -> Coupon:
        return self.coupons.create_coupon(code, prize_type, source)

    def record_session(self, mode_name: str) -> None:
        logger.info("Session recorded by compatibility API: %s", mode_name)

    def record_photo(self) -> None:
        logger.info("Photo recorded by compatibility API")

    async def broadcast_photo(self, photo_data: bytes, caption: str = "", source: str = "ARCADE") -> int:
        if not self.app or not self._running:
            return 0
        sent = 0
        for admin_id in ADMIN_IDS:
            try:
                await self.app.bot.send_photo(chat_id=admin_id, photo=photo_data, caption=caption or source)
                sent += 1
            except Exception as e:
                logger.warning("Could not broadcast compatibility photo: %s", e)
        return sent


class RemoteServer:
    def __init__(self, control: ArcadeControl, port: int = 8081) -> None:
        self.control = control
        self.port = port
        self.app = web.Application()
        self.app.router.add_get("/remote", self._handle_remote)
        self.app.router.add_get("/api/status", self._handle_status)
        self.app.router.add_get("/api/modes", self._handle_modes)
        self.app.router.add_post("/api/control", self._handle_control)
        self._runner: Optional[web.AppRunner] = None

    async def _handle_remote(self, request: web.Request) -> web.Response:
        remote_html = Path(__file__).parent / "remote.html"
        if remote_html.exists():
            return web.FileResponse(remote_html)
        return web.Response(text="Remote control not found", status=404)

    async def _handle_status(self, request: web.Request) -> web.Response:
        return web.json_response(self.control.status())

    async def _handle_modes(self, request: web.Request) -> web.Response:
        return web.json_response({"modes": ArcadeBot.get_available_mode_buttons()})

    async def _handle_control(self, request: web.Request) -> web.Response:
        data = await request.json()
        command = data.get("command", "")
        if command == "button":
            self.control.button(data.get("button", "start"))
        elif command == "start_mode":
            self.control.mode(data.get("mode", ""))
        elif command == "idle_next":
            self.control.idle_next()
        elif command == "idle_prev":
            self.control.idle_prev()
        elif command == "mute":
            self.control.mute()
        elif command == "unmute":
            self.control.unmute()
        elif command == "reboot":
            self.control.machine_reboot()
        else:
            return web.json_response({"error": "unknown command"}, status=400)
        return web.json_response({"ok": True})

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info("Remote server started on %s", self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()


_arcade_bot: Optional[ArcadeBot] = None
_remote_server: Optional[RemoteServer] = None


def get_arcade_bot() -> ArcadeBot:
    global _arcade_bot
    if _arcade_bot is None:
        _arcade_bot = ArcadeBot()
    return _arcade_bot


async def run_bot() -> None:
    global _remote_server
    bot = get_arcade_bot()
    _remote_server = RemoteServer(bot.control)
    await _remote_server.start()
    while True:
        try:
            await bot.start()
            break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram bot startup failed; retrying in 30 seconds")
            await bot.stop()
            await asyncio.sleep(30)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await bot.stop()
        if _remote_server:
            await _remote_server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(run_bot())
