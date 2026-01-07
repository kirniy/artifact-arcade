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
from artifact.hardware.printer import (
    create_label_printer,
    IP802Printer,
    MockLabelPrinter,
    # Legacy support
    create_printer,
    EM5820Printer,
)
from artifact.printing.label_receipt import LabelReceiptGenerator, LabelReceipt
from artifact.printing.receipt import ReceiptGenerator, Receipt

logger = logging.getLogger(__name__)

# Mode name translations for Telegram captions
MODE_NAMES_RU = {
    "sorting_hat": "🎩 Распределяющая Шляпа",
    "fortune": "🔮 Гадалка",
    "ai_prophet": "🧙 ИИ Пророк",
    "photobooth": "📸 Фотобудка",
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
}


class PrintManager:
    """Queue-based printing manager for thermal label stickers.

    Uses the AIYIN IP-802 label printer (58×100mm labels) as default.
    Falls back to EM5820 receipt printer if label printer unavailable.
    """

    def __init__(
        self,
        event_bus: EventBus,
        printer: Optional[Union[IP802Printer, EM5820Printer]] = None,
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

        if printer:
            self._printer = printer
            self._use_legacy = isinstance(printer, EM5820Printer)
        elif use_legacy_printer:
            self._printer = create_printer(mock=mock)
        else:
            self._printer = create_label_printer(mock=mock)

        # Choose appropriate receipt generator
        if self._use_legacy:
            self._generator = ReceiptGenerator()
        else:
            self._generator = LabelReceiptGenerator()

        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._telegram_bot = None  # Lazy-loaded to avoid circular imports

    @property
    def is_label_printer(self) -> bool:
        """Check if using label printer (not legacy receipt printer)."""
        return not self._use_legacy

    @property
    def printer_info(self) -> Dict[str, Any]:
        """Get printer information."""
        if hasattr(self._printer, 'get_status'):
            # IP802 has async get_status
            return {
                "type": "label" if self.is_label_printer else "receipt",
                "connected": self._printer.is_connected,
                "busy": self._printer.is_busy,
            }
        return {
            "type": "label" if self.is_label_printer else "receipt",
            "connected": getattr(self._printer, 'is_connected', False),
            "busy": getattr(self._printer, 'is_busy', False),
        }

    async def start(self) -> None:
        """Start the print manager and connect to the printer."""
        if self._running:
            return
        self._running = True
        await self._ensure_connected()
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"PrintManager started with {'label' if self.is_label_printer else 'receipt'} printer"
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
                    source="ARTIFACT ARCADE"
                )
                logger.info(f"Broadcast {mode_name} photo to Telegram")
            else:
                logger.debug(f"No image to broadcast for {mode_name}")

        except Exception as e:
            logger.error(f"Failed to broadcast to Telegram: {e}")

    def handle_print_start(self, event: Event) -> None:
        """Queue a print job from an event."""
        data = event.data if isinstance(event.data, dict) else {}
        try:
            self._queue.put_nowait(data)
            logger.info("Queued print job")
        except Exception as exc:
            logger.error(f"Failed to queue print job: {exc}")

    async def queue_print(self, data: Dict[str, Any]) -> None:
        """Queue a print job directly (async version)."""
        await self._queue.put(data)
        logger.info("Queued print job (async)")

    def queue_print_sync(self, data: Dict[str, Any]) -> bool:
        """Queue a print job synchronously. Returns True if successful."""
        try:
            self._queue.put_nowait(data)
            logger.info("Queued print job (sync)")
            return True
        except Exception as exc:
            logger.error(f"Failed to queue print job: {exc}")
            return False

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

            try:
                if not await self._ensure_connected():
                    raise RuntimeError("Printer not connected")

                mode_name = (
                    data.get("type") or
                    data.get("mode") or
                    data.get("mode_name") or
                    "generic"
                )

                # Generate receipt using appropriate generator
                receipt = self._generator.generate_receipt(mode_name, data)

                # Print the receipt
                ok = await self._print_receipt(receipt)

                if ok:
                    self._event_bus.emit(Event(
                        EventType.PRINT_COMPLETE,
                        data={"type": mode_name},
                        source="print_manager",
                    ))
                    # Broadcast to Telegram subscribers
                    await self._broadcast_to_telegram(mode_name, data)
                    logger.info(f"Printed {mode_name} label successfully")
                else:
                    raise RuntimeError("Printer rejected receipt")

            except Exception as exc:
                logger.error(f"Print failed: {exc}")
                self._event_bus.emit(Event(
                    EventType.PRINT_ERROR,
                    data={"error": str(exc)},
                    source="print_manager",
                ))
            finally:
                self._queue.task_done()

    async def _print_receipt(self, receipt: Union[LabelReceipt, Receipt]) -> bool:
        """Print a receipt/label.

        Handles both LabelReceipt (IP802) and Receipt (EM5820) formats.
        """
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
            await self._printer.print_text("=== ARTIFACT TEST ===")
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
            "printer_type": "label" if self.is_label_printer else "receipt",
        }

        if hasattr(self._printer, 'get_status'):
            printer_status = await self._printer.get_status()
            status.update(printer_status)
        else:
            status["connected"] = getattr(self._printer, 'is_connected', False)
            status["busy"] = getattr(self._printer, 'is_busy', False)

        return status
