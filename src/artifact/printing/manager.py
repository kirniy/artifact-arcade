"""Print manager for ARTIFACT thermal receipts."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any

from artifact.core.events import EventBus, Event, EventType
from artifact.hardware.printer import create_printer, EM5820Printer
from artifact.printing.receipt import ReceiptGenerator

logger = logging.getLogger(__name__)


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
