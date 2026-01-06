"""Print manager for ARTIFACT thermal receipts."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Optional, Dict, Any

from artifact.core.events import EventBus, Event, EventType
from artifact.hardware.printer import create_printer, EM5820Printer
from artifact.printing.receipt import ReceiptGenerator

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
}


class PrintManager:
    """Queue-based printing manager for thermal receipts."""

    def __init__(
        self,
        event_bus: EventBus,
        printer: Optional[EM5820Printer] = None,
        mock: bool = False,
    ) -> None:
        self._event_bus = event_bus
        self._printer = printer or create_printer(mock=mock)
        self._generator = ReceiptGenerator()
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._telegram_bot = None  # Lazy-loaded to avoid circular imports

    async def start(self) -> None:
        """Start the print manager and connect to the printer."""
        if self._running:
            return
        self._running = True
        await self._ensure_connected()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the print manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._printer:
            await self._printer.disconnect()

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

    async def _ensure_connected(self) -> bool:
        """Ensure printer is connected."""
        if not self._printer.is_connected:
            return await self._printer.connect()
        return True

    async def _run(self) -> None:
        """Process print jobs sequentially."""
        while self._running:
            data = await self._queue.get()
            try:
                if not await self._ensure_connected():
                    raise RuntimeError("Printer not connected")

                mode_name = (
                    data.get("type") or
                    data.get("mode") or
                    data.get("mode_name") or
                    "generic"
                )
                receipt = self._generator.generate_receipt(mode_name, data)
                ok = await self._printer.print_receipt(receipt)

                if ok:
                    self._event_bus.emit(Event(
                        EventType.PRINT_COMPLETE,
                        data={"type": mode_name},
                        source="print_manager",
                    ))
                    # Broadcast to Telegram subscribers
                    await self._broadcast_to_telegram(mode_name, data)
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
