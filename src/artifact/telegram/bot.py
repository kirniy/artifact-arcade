"""VNVNC Arcade Telegram Bot.

A Telegram bot for arcade management:
- Coupon verification and redemption for staff
- Photo/image broadcasting to subscribers
- Log access and statistics
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Set, List
from dataclasses import dataclass, field, asdict

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get("ARCADE_BOT_TOKEN", "7956425465:AAFRm30H40TVteVp8584I0F421BFJpAhr8A")
DATA_DIR = Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))
ADMIN_IDS: Set[int] = {433491, 804410245}  # Telegram IDs with full access
STAFF_IDS: Set[int] = {433491, 804410245, 429156227, 404497105}  # Staff who can validate coupons

# Control file for arcade communication
CONTROL_FILE = Path(os.environ.get("ARCADE_CONTROL_FILE", "/home/kirniy/modular-arcade/data/control.json"))


@dataclass
class Coupon:
    """A prize coupon."""
    code: str
    prize_type: str  # COCKTL, SHOTFR, etc.
    prize_label: str
    source: str  # ARCADE_QUIZ, ARCADE_SQUID, etc.
    created_at: str
    expires_at: str
    is_redeemed: bool = False
    redeemed_at: Optional[str] = None
    redeemed_by: Optional[int] = None  # Telegram ID of staff who redeemed


@dataclass
class ArcadeStats:
    """Arcade usage statistics."""
    total_sessions: int = 0
    sessions_today: int = 0
    coupons_issued: int = 0
    coupons_redeemed: int = 0
    photos_taken: int = 0
    last_activity: Optional[str] = None
    mode_counts: Dict[str, int] = field(default_factory=dict)


class CouponStore:
    """Persistent coupon storage using JSON file."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.coupons_file = data_dir / "coupons.json"
        self.stats_file = data_dir / "stats.json"
        self.subscribers_file = data_dir / "subscribers.json"
        self._coupons: Dict[str, Coupon] = {}
        self._stats = ArcadeStats()
        self._subscribers: Set[int] = set()
        self._load()

    def _load(self) -> None:
        """Load data from files."""
        # Load coupons
        if self.coupons_file.exists():
            try:
                with open(self.coupons_file, "r") as f:
                    data = json.load(f)
                    self._coupons = {
                        code: Coupon(**coupon_data)
                        for code, coupon_data in data.items()
                    }
                logger.info(f"Loaded {len(self._coupons)} coupons")
            except Exception as e:
                logger.error(f"Failed to load coupons: {e}")

        # Load stats
        if self.stats_file.exists():
            try:
                with open(self.stats_file, "r") as f:
                    data = json.load(f)
                    self._stats = ArcadeStats(**data)
                logger.info("Loaded arcade stats")
            except Exception as e:
                logger.error(f"Failed to load stats: {e}")

        # Load subscribers
        if self.subscribers_file.exists():
            try:
                with open(self.subscribers_file, "r") as f:
                    self._subscribers = set(json.load(f))
                logger.info(f"Loaded {len(self._subscribers)} subscribers")
            except Exception as e:
                logger.error(f"Failed to load subscribers: {e}")

    def _save_coupons(self) -> None:
        """Save coupons to file."""
        try:
            with open(self.coupons_file, "w") as f:
                json.dump(
                    {code: asdict(coupon) for code, coupon in self._coupons.items()},
                    f,
                    indent=2,
                    ensure_ascii=False
                )
        except Exception as e:
            logger.error(f"Failed to save coupons: {e}")

    def _save_stats(self) -> None:
        """Save stats to file."""
        try:
            with open(self.stats_file, "w") as f:
                json.dump(asdict(self._stats), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")

    def _save_subscribers(self) -> None:
        """Save subscribers to file."""
        try:
            with open(self.subscribers_file, "w") as f:
                json.dump(list(self._subscribers), f)
        except Exception as e:
            logger.error(f"Failed to save subscribers: {e}")

    def create_coupon(
        self,
        code: str,
        prize_type: str,
        prize_label: str,
        source: str,
        validity_days: int = 14,
    ) -> Coupon:
        """Create a new coupon."""
        now = datetime.now()
        expires = now + timedelta(days=validity_days)

        coupon = Coupon(
            code=code,
            prize_type=prize_type,
            prize_label=prize_label,
            source=source,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )

        self._coupons[code] = coupon
        self._stats.coupons_issued += 1
        self._save_coupons()
        self._save_stats()

        logger.info(f"Created coupon: {code} ({prize_label})")
        return coupon

    def get_coupon(self, code: str) -> Optional[Coupon]:
        """Get coupon by code."""
        return self._coupons.get(code.upper().strip())

    def validate_coupon(self, code: str) -> Dict[str, Any]:
        """Validate a coupon code."""
        code = code.upper().strip()
        coupon = self._coupons.get(code)

        if not coupon:
            return {"valid": False, "error": "NOT_FOUND", "message": "Купон не найден"}

        now = datetime.now()
        expires_at = datetime.fromisoformat(coupon.expires_at)

        if expires_at < now:
            return {
                "valid": False,
                "error": "EXPIRED",
                "message": "Купон истёк",
                "coupon": coupon,
            }

        if coupon.is_redeemed:
            return {
                "valid": False,
                "error": "ALREADY_REDEEMED",
                "message": "Купон уже использован",
                "coupon": coupon,
            }

        return {
            "valid": True,
            "coupon": coupon,
            "message": "Купон действителен",
        }

    def redeem_coupon(self, code: str, staff_id: int) -> Dict[str, Any]:
        """Redeem a coupon."""
        validation = self.validate_coupon(code)

        if not validation["valid"]:
            return validation

        coupon = validation["coupon"]
        coupon.is_redeemed = True
        coupon.redeemed_at = datetime.now().isoformat()
        coupon.redeemed_by = staff_id

        self._stats.coupons_redeemed += 1
        self._save_coupons()
        self._save_stats()

        logger.info(f"Redeemed coupon: {code} by staff {staff_id}")

        return {
            "success": True,
            "coupon": coupon,
            "message": "Купон погашен!",
        }

    def get_stats(self) -> ArcadeStats:
        """Get current stats."""
        return self._stats

    def update_stats(self, **kwargs) -> None:
        """Update stats."""
        for key, value in kwargs.items():
            if hasattr(self._stats, key):
                if isinstance(getattr(self._stats, key), int) and isinstance(value, int):
                    setattr(self._stats, key, getattr(self._stats, key) + value)
                else:
                    setattr(self._stats, key, value)
        self._stats.last_activity = datetime.now().isoformat()
        self._save_stats()

    def increment_mode(self, mode_name: str) -> None:
        """Increment mode play count."""
        self._stats.mode_counts[mode_name] = self._stats.mode_counts.get(mode_name, 0) + 1
        self._stats.total_sessions += 1
        self._stats.last_activity = datetime.now().isoformat()
        self._save_stats()

    def add_subscriber(self, user_id: int) -> bool:
        """Add a subscriber for photo broadcasts."""
        if user_id in self._subscribers:
            return False
        self._subscribers.add(user_id)
        self._save_subscribers()
        return True

    def remove_subscriber(self, user_id: int) -> bool:
        """Remove a subscriber."""
        if user_id not in self._subscribers:
            return False
        self._subscribers.discard(user_id)
        self._save_subscribers()
        return True

    def get_subscribers(self) -> Set[int]:
        """Get all subscribers."""
        return self._subscribers.copy()

    def get_recent_coupons(self, limit: int = 10) -> List[Coupon]:
        """Get recent coupons."""
        sorted_coupons = sorted(
            self._coupons.values(),
            key=lambda c: c.created_at,
            reverse=True
        )
        return sorted_coupons[:limit]


class ArcadeControl:
    """Control interface for arcade machine via shared file.

    Commands are written to control.json and read by the arcade main loop.
    """

    def __init__(self, control_file: Path = CONTROL_FILE):
        self.control_file = control_file
        self.control_file.parent.mkdir(parents=True, exist_ok=True)

    def _write_command(self, command: str, **kwargs) -> None:
        """Write a command to the control file."""
        data = {
            "command": command,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        try:
            with open(self.control_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Control command: {command} {kwargs}")
        except Exception as e:
            logger.error(f"Failed to write control command: {e}")

    def set_volume(self, level: float) -> None:
        """Set master volume (0.0 - 1.0)."""
        self._write_command("volume", level=max(0.0, min(1.0, level)))

    def volume_up(self, step: float = 0.1) -> None:
        """Increase volume."""
        self._write_command("volume_up", step=step)

    def volume_down(self, step: float = 0.1) -> None:
        """Decrease volume."""
        self._write_command("volume_down", step=step)

    def mute(self) -> None:
        """Mute audio."""
        self._write_command("mute")

    def unmute(self) -> None:
        """Unmute audio."""
        self._write_command("unmute")

    def toggle_mute(self) -> None:
        """Toggle mute state."""
        self._write_command("toggle_mute")

    def set_idle_scene(self, scene_index: int) -> None:
        """Set idle animation scene by index."""
        self._write_command("idle_scene", index=scene_index)

    def next_idle_scene(self) -> None:
        """Switch to next idle scene."""
        self._write_command("idle_next")

    def prev_idle_scene(self) -> None:
        """Switch to previous idle scene."""
        self._write_command("idle_prev")

    def start_mode(self, mode_name: str) -> None:
        """Start a specific mode."""
        self._write_command("start_mode", mode=mode_name)

    def press_button(self, button: str) -> None:
        """Simulate button press (start, left, right, back)."""
        valid_buttons = ["start", "left", "right", "back", "reboot"]
        if button.lower() in valid_buttons:
            self._write_command("button", button=button.lower())

    def reboot(self) -> None:
        """Reboot arcade to idle state."""
        self._write_command("reboot")

    def get_status(self) -> Dict[str, Any]:
        """Read current arcade status from status file."""
        status_file = self.control_file.parent / "status.json"
        if status_file.exists():
            try:
                with open(status_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


class ArcadeBot:
    """VNVNC Arcade Telegram Bot."""

    PRIZE_LABELS = {
        "COCKTL": "Бесплатный коктейль",
        "SHOTFR": "Бесплатный шот",
        "DEP5K": "Депозит 5000₽",
        "DEP10K": "Депозит 10000₽",
        "MERCHX": "Мерч VNVNC",
    }

    # Available modes for mode selection
    AVAILABLE_MODES = [
        "fortune", "ai_prophet", "photobooth", "roast",
        "squid_game", "quiz", "tower_stack", "brick_breaker", "video",
        "sorting_hat", "guess_me", "roulette", "autopsy"
    ]

    def __init__(self, token: str = BOT_TOKEN, data_dir: Path = DATA_DIR):
        self.token = token
        self.store = CouponStore(data_dir)
        self.control = ArcadeControl()
        self.app: Optional[Application] = None
        self._running = False

    async def start(self) -> None:
        """Start the bot."""
        logger.info("Starting VNVNC Arcade Bot...")

        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("check", self._cmd_check))
        self.app.add_handler(CommandHandler("redeem", self._cmd_redeem))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("subscribe", self._cmd_subscribe))
        self.app.add_handler(CommandHandler("unsubscribe", self._cmd_unsubscribe))
        self.app.add_handler(CommandHandler("recent", self._cmd_recent))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        # Admin control commands
        self.app.add_handler(CommandHandler("control", self._cmd_control))
        self.app.add_handler(CommandHandler("volume", self._cmd_volume))
        self.app.add_handler(CommandHandler("mute", self._cmd_mute))
        self.app.add_handler(CommandHandler("scene", self._cmd_scene))
        self.app.add_handler(CommandHandler("mode", self._cmd_mode))
        self.app.add_handler(CommandHandler("button", self._cmd_button))
        self.app.add_handler(CommandHandler("reboot", self._cmd_reboot))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("remote", self._cmd_remote))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        # Set bot commands
        await self.app.bot.set_my_commands([
            BotCommand("start", "Начать"),
            BotCommand("help", "Помощь"),
            BotCommand("check", "Проверить купон"),
            BotCommand("redeem", "Погасить купон"),
            BotCommand("stats", "Статистика"),
            BotCommand("subscribe", "Подписаться на фото"),
            BotCommand("unsubscribe", "Отписаться от фото"),
            BotCommand("recent", "Последние купоны"),
            BotCommand("control", "Панель управления"),
            BotCommand("status", "Статус аркады"),
            BotCommand("remote", "Пульт управления"),
        ])

        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        self._running = True
        logger.info("VNVNC Arcade Bot started!")

    async def stop(self) -> None:
        """Stop the bot."""
        if self.app and self._running:
            logger.info("Stopping VNVNC Arcade Bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self._running = False
            logger.info("VNVNC Arcade Bot stopped")

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in ADMIN_IDS

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user

        text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот аркадного автомата VNVNC ARCADE.\n\n"
            "🎟 <b>Для персонала:</b>\n"
            "/check <code>КОД</code> — проверить купон\n"
            "/redeem <code>КОД</code> — погасить купон\n"
            "/recent — последние купоны\n\n"
            "📸 <b>Для всех:</b>\n"
            "/subscribe — получать фото с аркады\n"
            "/stats — статистика автомата\n\n"
            "Или просто отправь код купона для проверки!"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        text = (
            "📖 <b>Команды бота:</b>\n\n"
            "<b>Проверка и погашение:</b>\n"
            "/check VNVNC-XXXX-XXXX-XXXX — проверить купон\n"
            "/redeem VNVNC-XXXX-XXXX-XXXX — погасить купон\n"
            "/recent — последние 10 купонов\n\n"
            "<b>Подписка на фото:</b>\n"
            "/subscribe — подписаться\n"
            "/unsubscribe — отписаться\n\n"
            "<b>Статистика:</b>\n"
            "/stats — статистика аркады\n\n"
            "💡 Можно просто отправить код купона!"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /check command - validate coupon."""
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите код купона:\n"
                "/check <code>VNVNC-XXXX-XXXX-XXXX</code>",
                parse_mode="HTML"
            )
            return

        code = context.args[0].upper().strip()
        await self._check_coupon(update, code)

    async def _cmd_redeem(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /redeem command - redeem coupon."""
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите код купона:\n"
                "/redeem <code>VNVNC-XXXX-XXXX-XXXX</code>",
                parse_mode="HTML"
            )
            return

        code = context.args[0].upper().strip()
        await self._redeem_coupon(update, code)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command."""
        stats = self.store.get_stats()

        mode_lines = []
        for mode, count in sorted(stats.mode_counts.items(), key=lambda x: -x[1]):
            mode_lines.append(f"  • {mode}: {count}")
        modes_text = "\n".join(mode_lines) if mode_lines else "  Нет данных"

        last_activity = "Нет данных"
        if stats.last_activity:
            try:
                dt = datetime.fromisoformat(stats.last_activity)
                last_activity = dt.strftime("%d.%m.%Y %H:%M")
            except:
                pass

        text = (
            "📊 <b>Статистика VNVNC ARCADE</b>\n\n"
            f"🎮 Всего сессий: <b>{stats.total_sessions}</b>\n"
            f"📸 Фото сделано: <b>{stats.photos_taken}</b>\n"
            f"🎟 Купонов выдано: <b>{stats.coupons_issued}</b>\n"
            f"✅ Купонов погашено: <b>{stats.coupons_redeemed}</b>\n"
            f"👥 Подписчиков: <b>{len(self.store.get_subscribers())}</b>\n\n"
            f"<b>По режимам:</b>\n{modes_text}\n\n"
            f"🕐 Последняя активность: {last_activity}"
        )

        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command."""
        user_id = update.effective_user.id

        if self.store.add_subscriber(user_id):
            await update.message.reply_text(
                "✅ Вы подписались на фото с аркады!\n"
                "Вы будете получать все фото и изображения, созданные на автомате."
            )
        else:
            await update.message.reply_text("Вы уже подписаны! 📸")

    async def _cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command."""
        user_id = update.effective_user.id

        if self.store.remove_subscriber(user_id):
            await update.message.reply_text("✅ Вы отписались от фото с аркады.")
        else:
            await update.message.reply_text("Вы не были подписаны.")

    async def _cmd_recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /recent command - show recent coupons."""
        coupons = self.store.get_recent_coupons(10)

        if not coupons:
            await update.message.reply_text("Нет купонов.")
            return

        lines = ["🎟 <b>Последние купоны:</b>\n"]

        for coupon in coupons:
            status = "✅" if coupon.is_redeemed else "🟡"
            try:
                created = datetime.fromisoformat(coupon.created_at).strftime("%d.%m %H:%M")
            except:
                created = "?"

            lines.append(
                f"{status} <code>{coupon.code}</code>\n"
                f"   {coupon.prize_label} • {created}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def _cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /logs command - admin only."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        # Try to read recent log entries
        log_file = Path("/home/kirniy/modular-arcade/logs/artifact.log")

        if not log_file.exists():
            await update.message.reply_text("Файл логов не найден.")
            return

        try:
            # Read last 50 lines
            with open(log_file, "r") as f:
                lines = f.readlines()[-50:]

            text = "📋 <b>Последние логи:</b>\n\n<pre>"
            text += "".join(lines)[-3500:]  # Telegram limit
            text += "</pre>"

            await update.message.reply_text(text, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"Ошибка чтения логов: {e}")

    # =========================================================================
    # ADMIN CONTROL COMMANDS
    # =========================================================================

    async def _cmd_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /control command - show control panel."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        keyboard = [
            [
                InlineKeyboardButton("🔊 Громче", callback_data="ctrl:vol_up"),
                InlineKeyboardButton("🔇 Тише", callback_data="ctrl:vol_down"),
            ],
            [
                InlineKeyboardButton("🔈 Вкл", callback_data="ctrl:unmute"),
                InlineKeyboardButton("🔇 Выкл", callback_data="ctrl:mute"),
            ],
            [
                InlineKeyboardButton("⬅️ Сцена", callback_data="ctrl:scene_prev"),
                InlineKeyboardButton("➡️ Сцена", callback_data="ctrl:scene_next"),
            ],
            [
                InlineKeyboardButton("⏪", callback_data="ctrl:btn_left"),
                InlineKeyboardButton("▶️ СТАРТ", callback_data="ctrl:btn_start"),
                InlineKeyboardButton("⏩", callback_data="ctrl:btn_right"),
            ],
            [
                InlineKeyboardButton("↩️ Назад", callback_data="ctrl:btn_back"),
                InlineKeyboardButton("🔄 Перезагрузка", callback_data="ctrl:reboot"),
            ],
        ]

        status = self.control.get_status()
        mode_name = status.get("mode", "idle")
        scene_name = status.get("idle_scene", "?")
        volume = status.get("volume", "?")
        muted = status.get("muted", False)

        text = (
            "🎮 <b>Панель управления VNVNC ARCADE</b>\n\n"
            f"📍 Режим: <code>{mode_name}</code>\n"
            f"🎬 Сцена: <code>{scene_name}</code>\n"
            f"🔊 Громкость: <code>{volume}</code>\n"
            f"🔇 Звук: {'выкл' if muted else 'вкл'}\n\n"
            "Выберите действие:"
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_volume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /volume command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        if not context.args:
            await update.message.reply_text(
                "Использование:\n"
                "/volume <number> - установить громкость (0-100)\n"
                "/volume up - увеличить\n"
                "/volume down - уменьшить"
            )
            return

        arg = context.args[0].lower()

        if arg == "up":
            self.control.volume_up()
            await update.message.reply_text("🔊 Громкость увеличена")
        elif arg == "down":
            self.control.volume_down()
            await update.message.reply_text("🔉 Громкость уменьшена")
        else:
            try:
                level = int(arg) / 100.0
                self.control.set_volume(level)
                await update.message.reply_text(f"🔊 Громкость: {int(level * 100)}%")
            except ValueError:
                await update.message.reply_text("❌ Неверное значение")

    async def _cmd_mute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /mute command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        arg = context.args[0].lower() if context.args else "toggle"

        if arg in ["on", "1", "да"]:
            self.control.mute()
            await update.message.reply_text("🔇 Звук выключен")
        elif arg in ["off", "0", "нет"]:
            self.control.unmute()
            await update.message.reply_text("🔊 Звук включен")
        else:
            self.control.toggle_mute()
            await update.message.reply_text("🔊 Звук переключен")

    async def _cmd_scene(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /scene command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        if not context.args:
            await update.message.reply_text(
                "Использование:\n"
                "/scene <number> - выбрать сцену\n"
                "/scene next - следующая\n"
                "/scene prev - предыдущая"
            )
            return

        arg = context.args[0].lower()

        if arg == "next":
            self.control.next_idle_scene()
            await update.message.reply_text("➡️ Следующая сцена")
        elif arg == "prev":
            self.control.prev_idle_scene()
            await update.message.reply_text("⬅️ Предыдущая сцена")
        else:
            try:
                index = int(arg)
                self.control.set_idle_scene(index)
                await update.message.reply_text(f"🎬 Сцена: {index}")
            except ValueError:
                await update.message.reply_text("❌ Неверное значение")

    async def _cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /mode command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        if not context.args:
            modes = "\n".join(f"• {m}" for m in self.AVAILABLE_MODES)
            await update.message.reply_text(
                f"Доступные режимы:\n{modes}\n\n"
                "Использование: /mode <название>"
            )
            return

        mode_name = context.args[0].lower()

        if mode_name in self.AVAILABLE_MODES:
            self.control.start_mode(mode_name)
            await update.message.reply_text(f"🎮 Запускаю режим: {mode_name}")
        else:
            await update.message.reply_text(f"❌ Неизвестный режим: {mode_name}")

    async def _cmd_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /button command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        if not context.args:
            await update.message.reply_text(
                "Кнопки:\n"
                "/button start - Старт/Подтвердить\n"
                "/button left - Влево\n"
                "/button right - Вправо\n"
                "/button back - Назад"
            )
            return

        button = context.args[0].lower()
        valid = ["start", "left", "right", "back", "reboot"]

        if button in valid:
            self.control.press_button(button)
            await update.message.reply_text(f"🎮 Нажата кнопка: {button}")
        else:
            await update.message.reply_text(f"❌ Неизвестная кнопка: {button}")

    async def _cmd_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reboot command."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        self.control.reboot()
        await update.message.reply_text("🔄 Аркада перезагружается в режим ожидания...")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        status = self.control.get_status()

        if not status:
            await update.message.reply_text(
                "📡 <b>Статус аркады</b>\n\n"
                "⚠️ Нет данных о статусе.\n"
                "Возможно, аркада не запущена.",
                parse_mode="HTML"
            )
            return

        mode = status.get("mode", "unknown")
        scene = status.get("idle_scene", "?")
        volume = status.get("volume", "?")
        muted = "🔇 Выкл" if status.get("muted") else "🔊 Вкл"
        uptime = status.get("uptime", "?")
        fps = status.get("fps", "?")

        await update.message.reply_text(
            f"📡 <b>Статус VNVNC ARCADE</b>\n\n"
            f"🎮 Режим: <code>{mode}</code>\n"
            f"🎬 Сцена: <code>{scene}</code>\n"
            f"🔊 Громкость: <code>{volume}</code>\n"
            f"🔈 Звук: {muted}\n"
            f"⏱ Аптайм: {uptime}\n"
            f"📊 FPS: {fps}",
            parse_mode="HTML"
        )

    async def _cmd_remote(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remote command - open web app remote control."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Только для администраторов")
            return

        # Get the Pi's hostname/IP for the remote URL
        remote_url = "http://artifact.local:8081/remote"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🎮 Открыть пульт",
                web_app=WebAppInfo(url=remote_url)
            )]
        ])

        await update.message.reply_text(
            "🕹️ <b>Пульт управления VNVNC ARCADE</b>\n\n"
            "Нажмите кнопку ниже, чтобы открыть пульт управления "
            "с полным контролем над аркадой.\n\n"
            f"📡 Прямая ссылка: {remote_url}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    # =========================================================================
    # MESSAGE HANDLERS
    # =========================================================================

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - check if it's a coupon code."""
        text = update.message.text.strip().upper()

        # Check if it looks like a coupon code
        if text.startswith("VNVNC-") or (len(text) >= 8 and "-" in text):
            await self._check_coupon(update, text)
        else:
            await update.message.reply_text(
                "Не понял. Отправьте код купона или используйте /help"
            )

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline buttons."""
        query = update.callback_query
        data = query.data

        # Handle control panel callbacks
        if data.startswith("ctrl:"):
            if not self.is_admin(query.from_user.id):
                await query.answer("⛔ Только для администраторов", show_alert=True)
                return

            action = data.split(":", 1)[1]
            response = "✅"

            if action == "vol_up":
                self.control.volume_up()
                response = "🔊 Громче"
            elif action == "vol_down":
                self.control.volume_down()
                response = "🔉 Тише"
            elif action == "mute":
                self.control.mute()
                response = "🔇 Звук выключен"
            elif action == "unmute":
                self.control.unmute()
                response = "🔊 Звук включен"
            elif action == "scene_next":
                self.control.next_idle_scene()
                response = "➡️ Следующая сцена"
            elif action == "scene_prev":
                self.control.prev_idle_scene()
                response = "⬅️ Предыдущая сцена"
            elif action == "btn_start":
                self.control.press_button("start")
                response = "▶️ СТАРТ"
            elif action == "btn_left":
                self.control.press_button("left")
                response = "⬅️"
            elif action == "btn_right":
                self.control.press_button("right")
                response = "➡️"
            elif action == "btn_back":
                self.control.press_button("back")
                response = "↩️ Назад"
            elif action == "reboot":
                self.control.reboot()
                response = "🔄 Перезагрузка..."

            await query.answer(response)
            return

        await query.answer()

        if data.startswith("redeem:"):
            code = data.split(":", 1)[1]
            result = self.store.redeem_coupon(code, query.from_user.id)

            if result.get("success"):
                coupon = result["coupon"]
                await query.edit_message_text(
                    f"✅ <b>Купон погашен!</b>\n\n"
                    f"🎟 Код: <code>{coupon.code}</code>\n"
                    f"🎁 Приз: {coupon.prize_label}\n"
                    f"👤 Погасил: {query.from_user.first_name}",
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text(
                    f"❌ {result.get('message', 'Ошибка')}",
                    parse_mode="HTML"
                )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _check_coupon(self, update: Update, code: str) -> None:
        """Check a coupon and show result with redeem button."""
        result = self.store.validate_coupon(code)

        if not result["valid"]:
            error = result.get("error", "UNKNOWN")
            coupon = result.get("coupon")

            if error == "NOT_FOUND":
                text = f"❌ Купон <code>{code}</code> не найден"
            elif error == "EXPIRED":
                text = f"⏰ Купон <code>{code}</code> истёк"
            elif error == "ALREADY_REDEEMED":
                redeemed_at = "?"
                if coupon and coupon.redeemed_at:
                    try:
                        dt = datetime.fromisoformat(coupon.redeemed_at)
                        redeemed_at = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        pass
                text = (
                    f"⚠️ Купон уже использован!\n\n"
                    f"🎟 Код: <code>{code}</code>\n"
                    f"🎁 Приз: {coupon.prize_label if coupon else '?'}\n"
                    f"📅 Погашен: {redeemed_at}"
                )
            else:
                text = f"❌ {result.get('message', 'Ошибка')}"

            await update.message.reply_text(text, parse_mode="HTML")
            return

        coupon = result["coupon"]
        expires_at = "?"
        try:
            dt = datetime.fromisoformat(coupon.expires_at)
            expires_at = dt.strftime("%d.%m.%Y %H:%M")
        except:
            pass

        text = (
            f"✅ <b>Купон действителен!</b>\n\n"
            f"🎟 Код: <code>{coupon.code}</code>\n"
            f"🎁 Приз: <b>{coupon.prize_label}</b>\n"
            f"📍 Источник: {coupon.source}\n"
            f"⏰ Действует до: {expires_at}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Погасить", callback_data=f"redeem:{coupon.code}")]
        ])

        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

    async def _redeem_coupon(self, update: Update, code: str) -> None:
        """Redeem a coupon directly."""
        result = self.store.redeem_coupon(code, update.effective_user.id)

        if result.get("success"):
            coupon = result["coupon"]
            await update.message.reply_text(
                f"✅ <b>Купон погашен!</b>\n\n"
                f"🎟 Код: <code>{coupon.code}</code>\n"
                f"🎁 Приз: {coupon.prize_label}",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ {result.get('message', 'Ошибка погашения')}",
                parse_mode="HTML"
            )

    # =========================================================================
    # PUBLIC API (called by arcade)
    # =========================================================================

    def create_coupon(
        self,
        code: str,
        prize_type: str,
        source: str = "ARCADE",
    ) -> Coupon:
        """Create a new coupon (called by arcade on prize win)."""
        prize_label = self.PRIZE_LABELS.get(prize_type, prize_type)
        return self.store.create_coupon(
            code=code,
            prize_type=prize_type,
            prize_label=prize_label,
            source=source,
        )

    def record_session(self, mode_name: str) -> None:
        """Record a game session."""
        self.store.increment_mode(mode_name)

    def record_photo(self) -> None:
        """Record a photo taken."""
        self.store.update_stats(photos_taken=1)

    async def broadcast_photo(
        self,
        photo_data: bytes,
        caption: str = "",
        source: str = "ARCADE",
    ) -> int:
        """Broadcast a photo to all subscribers. Returns count sent."""
        if not self.app or not self._running:
            logger.warning("Bot not running, cannot broadcast")
            return 0

        subscribers = self.store.get_subscribers()
        sent = 0

        for user_id in subscribers:
            try:
                await self.app.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_data,
                    caption=f"📸 {caption}\n\n🎮 {source}" if caption else f"📸 🎮 {source}",
                )
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send photo to {user_id}: {e}")

        logger.info(f"Broadcast photo to {sent}/{len(subscribers)} subscribers")
        return sent

    async def notify_admins(self, message: str) -> None:
        """Send notification to admins."""
        if not self.app or not self._running:
            return

        for admin_id in ADMIN_IDS:
            try:
                await self.app.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")


# =============================================================================
# WEB SERVER FOR REMOTE CONTROL
# =============================================================================

class RemoteServer:
    """HTTP server for remote control web app."""

    def __init__(self, control: ArcadeControl, port: int = 8081):
        self.control = control
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self._runner: Optional[web.AppRunner] = None

    def _setup_routes(self) -> None:
        """Setup HTTP routes."""
        self.app.router.add_get("/remote", self._handle_remote)
        self.app.router.add_get("/api/status", self._handle_status)
        self.app.router.add_post("/api/control", self._handle_control)

    async def _handle_remote(self, request: web.Request) -> web.Response:
        """Serve the remote control HTML."""
        remote_html = Path(__file__).parent / "remote.html"
        if remote_html.exists():
            return web.FileResponse(remote_html)
        return web.Response(text="Remote control not found", status=404)

    async def _handle_status(self, request: web.Request) -> web.Response:
        """Return arcade status."""
        status = self.control.get_status()
        return web.json_response(status)

    async def _handle_control(self, request: web.Request) -> web.Response:
        """Handle control commands."""
        try:
            data = await request.json()
            command = data.get("command")
            message = "OK"

            if command == "button":
                button = data.get("button", "start")
                self.control.press_button(button)
                message = f"Button: {button}"
            elif command == "volume":
                level = float(data.get("level", 1.0))
                self.control.set_volume(level)
                message = f"Volume: {int(level * 100)}%"
            elif command == "volume_up":
                self.control.volume_up()
                message = "Volume up"
            elif command == "volume_down":
                self.control.volume_down()
                message = "Volume down"
            elif command == "mute":
                self.control.mute()
                message = "Muted"
            elif command == "unmute":
                self.control.unmute()
                message = "Unmuted"
            elif command == "toggle_mute":
                self.control.toggle_mute()
                message = "Mute toggled"
            elif command == "idle_next":
                self.control.next_idle_scene()
                message = "Next scene"
            elif command == "idle_prev":
                self.control.prev_idle_scene()
                message = "Previous scene"
            elif command == "idle_scene":
                index = int(data.get("index", 0))
                self.control.set_idle_scene(index)
                message = f"Scene: {index}"
            elif command == "start_mode":
                mode = data.get("mode", "")
                self.control.start_mode(mode)
                message = f"Mode: {mode}"
            elif command == "reboot":
                self.control.reboot()
                message = "Rebooting..."
            else:
                return web.json_response({"error": "Unknown command"}, status=400)

            return web.json_response({"success": True, "message": message})

        except Exception as e:
            logger.error(f"Control error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def start(self) -> None:
        """Start the web server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Remote control server started on port {self.port}")

    async def stop(self) -> None:
        """Stop the web server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Remote control server stopped")


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_arcade_bot: Optional[ArcadeBot] = None
_remote_server: Optional[RemoteServer] = None


def get_arcade_bot() -> ArcadeBot:
    """Get or create global bot instance."""
    global _arcade_bot
    if _arcade_bot is None:
        _arcade_bot = ArcadeBot()
    return _arcade_bot


async def run_bot() -> None:
    """Run the bot and remote control server."""
    global _remote_server

    bot = get_arcade_bot()

    # Start remote control server
    _remote_server = RemoteServer(bot.control)
    await _remote_server.start()

    # Start bot
    await bot.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await bot.stop()
        if _remote_server:
            await _remote_server.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_bot())
