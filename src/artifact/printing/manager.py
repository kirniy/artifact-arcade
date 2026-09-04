"""Print manager for ARTIFACT thermal label stickers.

Manages printing on the AIYIN IP-802 thermal label printer with
58×100mm self-adhesive labels. Handles print queue, Telegram
broadcasting, and error recovery.
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Optional, Dict, Any, Union

from artifact.core.events import EventBus, Event, EventType
from artifact.hardware.printer.em5820 import EM5820Printer, create_printer
from artifact.hardware.printer.ip802 import IP802Printer, MockLabelPrinter, create_label_printer
from artifact.hardware.printer.rp80 import (
    MockRP80ReceiptPrinter,
    RP80ReceiptPrinter,
    auto_detect_rp80_printer,
    create_rp80_printer,
)
from artifact.printing.label_receipt import LabelReceiptGenerator, LabelReceipt
from artifact.printing.photobooth_roll import PhotoboothRollReceipt, PhotoboothRollReceiptGenerator
from artifact.printing.receipt import ReceiptGenerator, Receipt
from artifact.printing.wheel_prize_roll import (
    WHEEL_PRIZE_MODE_NAME,
    WheelPrizeRollReceipt,
    WheelPrizeRollReceiptGenerator,
)
from artifact.printing.spiderverse_quest_roll import (
    SPIDERVERSE_QUEST_MODE_NAME,
    SpiderverseQuestRollReceipt,
    SpiderverseQuestRollReceiptGenerator,
)

logger = logging.getLogger(__name__)

# Mode name translations for Telegram captions
MODE_NAMES_RU = {
    "sorting_hat": "🎩 Распределяющая Шляпа",
    "fortune": "🔮 Гадалка",
    "ai_prophet": "🧙 ИИ Пророк",
    "photobooth": "📸 Фотобудка",
    "brainrot_booth": "🧠 Брейнрот",
    "wedding_booth": "💒 Фавтфаа Пэпэ",
    "whatsapp_booth": "💚 Пэпэшнейше",
    "roast": "🔥 Прожарка",
    "guess_me": "🎭 Кто Я?",
    "squid_game": "🦑 Игра в Кальмара",
    "quiz": "❓ Викторина",
    "autopsy": "🩻 Диагноз",
    "roulette": "🎰 Рулетка",
    "zodiac": "⭐ Зодиак",
    "rap_god": "🎤 Рэп Бог",
    "tower_stack": "🏗️ Башня",
    "brick_breaker": "🧱 Кирпичи",
    "video": "🎬 Видео",
    WHEEL_PRIZE_MODE_NAME: "🎁 Барабан призов",
    SPIDERVERSE_QUEST_MODE_NAME: "🕸 ПАУЧЬЕ ЧУТЬЁ",
}


class PrintManager:
    """Queue-based printing manager for thermal label stickers.

    Uses the RP80 receipt printer for photobooth when present, otherwise the
    AIYIN IP-802 label printer. Falls back to EM5820 only when explicitly
    requested with ARTIFACT_USE_LEGACY_PRINTER=true.
    """

    def __init__(
        self,
        event_bus: EventBus,
        printer: Optional[Union[IP802Printer, EM5820Printer, RP80ReceiptPrinter]] = None,
        mock: bool = False,
        use_legacy_printer: bool = False,
    ) -> None:
        """Initialize print manager.

        Args:
            event_bus: Event bus for print events
            printer: Optional pre-configured printer instance
            mock: If True, use mock printer for testing
            use_legacy_printer: If True, use EM5820 receipt printer instead of IP802
        """
        self._event_bus = event_bus
        self._use_legacy = use_legacy_printer
        self._use_rp80 = False
        self._mock_requested = mock

        if printer:
            self._printer = printer
            self._use_legacy = isinstance(printer, EM5820Printer)
            self._use_rp80 = isinstance(printer, RP80ReceiptPrinter)
        elif use_legacy_printer:
            self._printer = create_printer(mock=mock)
        elif not mock and auto_detect_rp80_printer():
            self._printer = create_rp80_printer(mock=False)
            self._use_rp80 = True
        else:
            self._printer = create_label_printer(mock=mock)

        # Choose appropriate receipt generator
        if self._use_rp80:
            self._generator = PhotoboothRollReceiptGenerator()
        elif self._use_legacy:
            self._generator = ReceiptGenerator()
        else:
            self._generator = LabelReceiptGenerator()

        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._telegram_bot = None  # Lazy-loaded to avoid circular imports
        # Prize issue IDs are server-authoritative idempotency keys.  Keep a
        # small in-memory ledger so repeated UI/events cannot print a second
        # redeemable receipt for the same issue during this process lifetime.
        self._pending_print_keys: set[str] = set()
        self._completed_print_keys: dict[str, None] = {}
        self._completed_print_key_limit = 256

    async def _select_rp80_printer(self, *, mock: bool = False) -> bool:
        """Switch this manager to the RP80 receipt printer when USB is present."""
        detected = None if mock else auto_detect_rp80_printer()
        if not mock and not detected:
            return False

        if self._printer and getattr(self._printer, "is_connected", False):
            try:
                await self._printer.disconnect()
            except Exception as exc:
                logger.debug("Ignoring disconnect error while switching to RP80: %s", exc)

        # Pass the already-resolved device through directly.  Calling the
        # factory after detection creates a race where a vanished device used
        # to turn into a silent mock printer.
        self._printer = (
            MockRP80ReceiptPrinter()
            if mock
            else RP80ReceiptPrinter(port=detected)
        )
        self._generator = PhotoboothRollReceiptGenerator()
        self._use_legacy = False
        self._use_rp80 = True
        logger.info("RP80 receipt printer selected for 80mm roll output")
        return True

    async def _maybe_select_rp80_for_job(self, mode_name: str) -> None:
        """Hot-plug RP80 for the two modes that own 80mm roll layouts."""
        if mode_name not in {
            "photobooth",
            WHEEL_PRIZE_MODE_NAME,
            SPIDERVERSE_QUEST_MODE_NAME,
        } or self._use_rp80:
            return
        if self._mock_requested:
            await self._select_rp80_printer(mock=True)
            return
        await self._select_rp80_printer(mock=False)

    @property
    def is_label_printer(self) -> bool:
        """Check if using label printer (not legacy receipt printer)."""
        return not self._use_legacy and not self._use_rp80

    @property
    def is_rp80_printer(self) -> bool:
        """Check if using the RP80 photobooth receipt printer."""
        return self._use_rp80

    @property
    def printer_info(self) -> Dict[str, Any]:
        """Get printer information."""
        if hasattr(self._printer, 'get_status'):
            # IP802 has async get_status
            return {
                "type": "rp80" if self.is_rp80_printer else "label" if self.is_label_printer else "receipt",
                "connected": self._printer.is_connected,
                "busy": self._printer.is_busy,
            }
        return {
            "type": "rp80" if self.is_rp80_printer else "label" if self.is_label_printer else "receipt",
            "connected": getattr(self._printer, 'is_connected', False),
            "busy": getattr(self._printer, 'is_busy', False),
        }

    async def start(self) -> None:
        """Start the print manager and connect to the printer."""
        if self._running:
            return
        self._running = True
        if not await self._ensure_connected():
            logger.warning("Printer not connected at startup; printing remains optional until a printer appears")
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"PrintManager started with {'rp80' if self.is_rp80_printer else 'label' if self.is_label_printer else 'receipt'} printer"
        )

    async def stop(self) -> None:
        """Stop the print manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._printer:
            await self._printer.disconnect()
        logger.info("PrintManager stopped")

    def _get_telegram_bot(self):
        """Get Telegram bot instance (lazy load to avoid circular import)."""
        if self._telegram_bot is None:
            try:
                from artifact.telegram import get_arcade_bot
                self._telegram_bot = get_arcade_bot()
            except Exception as e:
                logger.warning(f"Failed to get Telegram bot: {e}")
                return None
        return self._telegram_bot

    def _extract_image_bytes(self, data: Dict[str, Any]) -> Optional[bytes]:
        """Extract image bytes from print data.

        Looks for common image fields: caricature, portrait, photo, sketch, doodle, scan_image
        """
        # Try various image field names
        image_fields = ["caricature", "portrait", "photo", "sketch", "doodle", "scan_image"]

        for field in image_fields:
            image = data.get(field)
            if image is None:
                continue

            # Already bytes
            if isinstance(image, (bytes, bytearray)):
                return bytes(image)

            # NumPy array - convert to PNG
            try:
                import numpy as np
                from PIL import Image

                if isinstance(image, np.ndarray):
                    img = Image.fromarray(image)
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Failed to convert image from {field}: {e}")
                continue

            # PIL Image
            try:
                from PIL import Image
                if isinstance(image, Image.Image):
                    buf = BytesIO()
                    image.save(buf, format="PNG")
                    return buf.getvalue()
            except Exception:
                pass

        return None

    async def _broadcast_to_telegram(self, mode_name: str, data: Dict[str, Any]) -> None:
        """Broadcast image and session info to Telegram subscribers."""
        bot = self._get_telegram_bot()
        if not bot:
            return

        try:
            # Record the session play
            bot.record_session(mode_name)

            # Extract image for broadcasting
            image_bytes = self._extract_image_bytes(data)
            if image_bytes:
                # Build caption with mode name and any relevant info
                caption_parts = [MODE_NAMES_RU.get(mode_name, mode_name.upper())]

                # Add house name for sorting_hat
                if mode_name == "sorting_hat":
                    house = data.get("house_name_ru") or data.get("house_ru") or data.get("house")
                    if house:
                        caption_parts.append(f"Факультет: {house}")

                # Add prediction/fortune text (full)
                for text_field in ["prediction", "fortune", "roast", "diagnosis", "display_text"]:
                    text = data.get(text_field)
                    if text and isinstance(text, str):
                        caption_parts.append(text)
                        break

                # Add download URL if available
                short_url = data.get("short_url") or data.get("qr_url")
                if short_url:
                    caption_parts.append(f"📥 {short_url}")

                caption = "\n\n".join(caption_parts)

                # Broadcast photo
                await bot.broadcast_photo(
                    photo_data=image_bytes,
                    caption=caption,
                    source="ФОТОБУДКА ВИНОВНИЦЫ"
                )
                logger.info(f"Broadcast {mode_name} photo to Telegram")
            else:
                logger.debug(f"No image to broadcast for {mode_name}")

        except Exception as e:
            logger.error(f"Failed to broadcast to Telegram: {e}")

    def handle_print_start(self, event: Event) -> None:
        """Queue a print job from an event."""
        data = event.data if isinstance(event.data, dict) else {}
        job_key = self._claim_print_job(data)
        if job_key is False:
            return
        try:
            self._queue.put_nowait(data)
            logger.info("Queued print job")
        except Exception as exc:
            self._release_print_job(job_key)
            logger.error(f"Failed to queue print job: {exc}")

    async def queue_print(self, data: Dict[str, Any]) -> None:
        """Queue a print job directly (async version)."""
        job_key = self._claim_print_job(data)
        if job_key is False:
            return
        try:
            await self._queue.put(data)
        except Exception:
            self._release_print_job(job_key)
            raise
        logger.info("Queued print job (async)")

    def queue_print_sync(self, data: Dict[str, Any]) -> bool:
        """Queue a print job synchronously. Returns True if successful."""
        job_key = self._claim_print_job(data)
        if job_key is False:
            return True
        try:
            self._queue.put_nowait(data)
            logger.info("Queued print job (sync)")
            return True
        except Exception as exc:
            self._release_print_job(job_key)
            logger.error(f"Failed to queue print job: {exc}")
            return False

    def _prize_print_job_key(self, data: Dict[str, Any]) -> Optional[str]:
        mode_name = data.get("type") or data.get("mode") or data.get("mode_name")
        if mode_name not in {WHEEL_PRIZE_MODE_NAME, SPIDERVERSE_QUEST_MODE_NAME}:
            return None
        value = str(data.get("print_job_key") or data.get("issue_id") or "").strip()
        return value or None

    def _claim_print_job(self, data: Dict[str, Any]) -> Optional[str] | bool:
        """Reserve a prize print key; ``False`` means an idempotent duplicate."""
        key = self._prize_print_job_key(data)
        if key is None:
            return None
        if key in self._pending_print_keys or key in self._completed_print_keys:
            logger.warning("Ignoring duplicate prize print job: %s", key)
            return False
        self._pending_print_keys.add(key)
        return key

    def _release_print_job(self, key: Optional[str] | bool) -> None:
        if isinstance(key, str):
            self._pending_print_keys.discard(key)

    def _complete_print_job(self, key: Optional[str]) -> None:
        if key is None:
            return
        self._pending_print_keys.discard(key)
        self._completed_print_keys[key] = None
        while len(self._completed_print_keys) > self._completed_print_key_limit:
            self._completed_print_keys.pop(next(iter(self._completed_print_keys)))

    async def _ensure_connected(self) -> bool:
        """Ensure printer is connected."""
        if not self._printer.is_connected:
            return await self._printer.connect()
        return True

    async def _run(self) -> None:
        """Process print jobs sequentially."""
        while self._running:
            try:
                data = await self._queue.get()
            except asyncio.CancelledError:
                break

            print_job_key = self._prize_print_job_key(data)
            print_succeeded = False
            try:
                mode_name = (
                    data.get("type") or
                    data.get("mode") or
                    data.get("mode_name") or
                    "generic"
                )
                await self._maybe_select_rp80_for_job(mode_name)

                if mode_name in {WHEEL_PRIZE_MODE_NAME, SPIDERVERSE_QUEST_MODE_NAME} and not self._use_rp80:
                    raise RuntimeError(f"RP80 receipt printer is required for {mode_name}")

                if not await self._ensure_connected():
                    if mode_name == "photobooth" and not data.get("print_required"):
                        logger.warning("Photobooth print skipped because optional printer is not connected")
                        continue
                    raise RuntimeError("Printer not connected")

                # Generate receipt using appropriate generator. The RP80 layout is
                # intentionally photobooth-specific; other modes still use the
                # generic receipt renderer if they reach this printer.
                if mode_name == WHEEL_PRIZE_MODE_NAME:
                    receipt = WheelPrizeRollReceiptGenerator().generate_receipt(mode_name, data)
                elif mode_name == SPIDERVERSE_QUEST_MODE_NAME:
                    receipt = SpiderverseQuestRollReceiptGenerator().generate_receipt(mode_name, data)
                elif self._use_rp80 and mode_name != "photobooth":
                    receipt = ReceiptGenerator().generate_receipt(mode_name, data)
                else:
                    receipt = self._generator.generate_receipt(mode_name, data)

                # Print the receipt
                ok = await self._print_receipt(receipt)

                if ok:
                    print_succeeded = True
                    self._complete_print_job(print_job_key)
                    self._event_bus.emit(Event(
                        EventType.PRINT_COMPLETE,
                        data={
                            "type": mode_name,
                            "issue_id": data.get("issue_id"),
                            "print_job_key": print_job_key,
                        },
                        source="print_manager",
                    ))
                    # Broadcast to Telegram subscribers
                    await self._broadcast_to_telegram(mode_name, data)
                    logger.info(f"Printed {mode_name} successfully")
                else:
                    if (
                        self._use_rp80
                        and mode_name == "photobooth"
                        and not data.get("print_required")
                    ):
                        logger.warning("Photobooth print skipped because RP80 did not accept the job")
                        continue
                    raise RuntimeError("Printer rejected receipt")

            except Exception as exc:
                logger.error(f"Print failed: {exc}")
                self._event_bus.emit(Event(
                    EventType.PRINT_ERROR,
                    data={
                        "type": data.get("type") or data.get("mode") or data.get("mode_name"),
                        "issue_id": data.get("issue_id"),
                        "print_job_key": print_job_key,
                        "error": str(exc),
                    },
                    source="print_manager",
                ))
            finally:
                if not print_succeeded:
                    self._release_print_job(print_job_key)
                self._queue.task_done()

    async def _print_receipt(
        self,
        receipt: Union[
            LabelReceipt,
            Receipt,
            PhotoboothRollReceipt,
            WheelPrizeRollReceipt,
            SpiderverseQuestRollReceipt,
        ],
    ) -> bool:
        """Print a receipt/label.

        Handles both LabelReceipt (IP802) and Receipt (EM5820) formats.
        """
        if isinstance(receipt, WheelPrizeRollReceipt):
            if not isinstance(self._printer, RP80ReceiptPrinter):
                logger.error("Refusing to route a redeemable prize receipt outside RP80")
                return False
            return await self._printer.print_raw(receipt.raw_commands)

        if isinstance(receipt, SpiderverseQuestRollReceipt):
            if not isinstance(self._printer, RP80ReceiptPrinter):
                logger.error("Refusing to route a quest receipt outside RP80")
                return False
            return await self._printer.print_raw(receipt.raw_commands)

        if isinstance(receipt, PhotoboothRollReceipt):
            if isinstance(self._printer, RP80ReceiptPrinter):
                return await self._printer.print_raw(receipt.raw_commands)
            return await self._printer.print_raw(receipt.raw_commands)

        if isinstance(receipt, LabelReceipt):
            # Label printer - send raw commands directly
            if isinstance(self._printer, IP802Printer):
                return await self._printer.print_raw(receipt.raw_commands)
            elif isinstance(self._printer, MockLabelPrinter):
                # Mock mode - log preview
                logger.info(f"=== MOCK LABEL PRINT: {receipt.mode_name} ===")
                if receipt.preview_image:
                    logger.info(f"Preview image: {len(receipt.preview_image)} bytes")
                return True
            else:
                # Fallback for unexpected printer type
                return await self._printer.print_raw(receipt.raw_commands)
        else:
            # Legacy receipt - use print_receipt method
            return await self._printer.print_receipt(receipt)

    async def print_test_label(self) -> bool:
        """Print a test label to verify printer is working.

        Returns:
            True if test label printed successfully
        """
        if not await self._ensure_connected():
            logger.error("Cannot print test label - printer not connected")
            return False

        if isinstance(self._printer, IP802Printer):
            return await self._printer.self_test()
        else:
            # Legacy printer test
            await self._printer.print_text("=== ФОТОБУДКА ВИНОВНИЦЫ TEST ===")
            await self._printer.print_text("Printer is working!")
            await self._printer.feed_paper(3)
            return True

    async def get_status(self) -> Dict[str, Any]:
        """Get current printer status.

        Returns:
            Status dictionary with connection and job info
        """
        status = {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "printer_type": "rp80" if self.is_rp80_printer else "label" if self.is_label_printer else "receipt",
        }

        if hasattr(self._printer, 'get_status'):
            printer_status = await self._printer.get_status()
            status.update(printer_status)
        else:
            status["connected"] = getattr(self._printer, 'is_connected', False)
            status["busy"] = getattr(self._printer, 'is_busy', False)

        return status
