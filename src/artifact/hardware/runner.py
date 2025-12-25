"""
Hardware runner for ARTIFACT on Raspberry Pi.

Manages real hardware: HDMI display (via T50), WS2812B LEDs,
I2C LCD, GPIO inputs, camera, and thermal printer.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

from ..core.state import StateMachine
from ..core.events import EventBus, EventType, Event
from ..audio.engine import get_audio_engine

logger = logging.getLogger(__name__)

# Pygame is used for HDMI output and event handling
_pygame = None


def _get_pygame():
    """Lazy import pygame."""
    global _pygame
    if _pygame is None:
        import pygame
        _pygame = pygame
    return _pygame


@dataclass
class HardwareConfig:
    """Hardware configuration."""
    # Display settings
    main_width: int = 128
    main_height: int = 128
    ticker_width: int = 48
    ticker_height: int = 8
    lcd_cols: int = 16
    lcd_rows: int = 2

    # GPIO settings
    ws2812b_gpio: int = 21  # Not 18 to avoid audio conflict
    ws2812b_brightness: int = 128

    # I2C settings
    lcd_i2c_address: int = 0x27
    lcd_i2c_bus: int = 1

    # Frame rate
    fps: int = 60


class HardwareRunner:
    """
    Hardware runner for Raspberry Pi deployment.

    Initializes and manages:
    - HDMI display (128x128 output to NovaStar T50)
    - WS2812B LED strip (48x8 ticker via GPIO 21)
    - I2C LCD (16x2 character display)
    - GPIO inputs (arcade buttons, keypad)
    - Camera (Raspberry Pi Camera Module 3)
    - Thermal printer (ESC/POS via UART)
    - Audio (pygame mixer via 3.5mm jack)
    """

    def __init__(
        self,
        config: HardwareConfig | None = None,
        state_machine: StateMachine | None = None,
        event_bus: EventBus | None = None
    ) -> None:
        self.config = config or HardwareConfig()
        self.state_machine = state_machine or StateMachine()
        self.event_bus = event_bus or EventBus()

        # Hardware references
        self._main_display = None
        self._ticker_display = None
        self._lcd_display = None
        self._audio_engine = None

        # State
        self._running = False
        self._frame_count = 0
        self._clock = None
        self._initialized = False

        # Use mock displays if hardware unavailable
        self._use_mocks = os.getenv("ARTIFACT_MOCK_HARDWARE", "false").lower() == "true"

        logger.info("HardwareRunner created")

    def _init_displays(self) -> bool:
        """Initialize all display hardware."""
        success = True

        # Main display (HDMI via T50)
        try:
            if self._use_mocks:
                from .display import HDMIDisplayScaled
                # Use scaled version for testing on regular monitor
                self._main_display = HDMIDisplayScaled(
                    width=self.config.main_width,
                    height=self.config.main_height,
                    scale=4  # 512x512 output
                )
            else:
                from .display import HDMIDisplay
                self._main_display = HDMIDisplay(
                    width=self.config.main_width,
                    height=self.config.main_height
                )

            if not self._main_display.init():
                logger.error("Failed to initialize HDMI display")
                success = False
        except Exception as e:
            logger.error(f"HDMI display init error: {e}")
            success = False

        # Ticker display (WS2812B)
        try:
            if self._use_mocks:
                from .display import WS2812BDisplayMock
                self._ticker_display = WS2812BDisplayMock(
                    width=self.config.ticker_width,
                    height=self.config.ticker_height
                )
            else:
                from .display import WS2812BDisplay
                self._ticker_display = WS2812BDisplay(
                    width=self.config.ticker_width,
                    height=self.config.ticker_height,
                    brightness=self.config.ws2812b_brightness,
                    gpio_pin=self.config.ws2812b_gpio
                )

            if hasattr(self._ticker_display, 'init'):
                if not self._ticker_display.init():
                    logger.warning("WS2812B display init returned False")
        except Exception as e:
            logger.warning(f"WS2812B display init error: {e}")
            # Non-fatal - can run without ticker

        # LCD display (I2C)
        try:
            if self._use_mocks:
                from .display import I2CLCDDisplayMock
                self._lcd_display = I2CLCDDisplayMock(
                    cols=self.config.lcd_cols,
                    rows=self.config.lcd_rows
                )
            else:
                from .display import I2CLCDDisplay
                self._lcd_display = I2CLCDDisplay(
                    cols=self.config.lcd_cols,
                    rows=self.config.lcd_rows,
                    i2c_address=self.config.lcd_i2c_address,
                    i2c_bus=self.config.lcd_i2c_bus
                )

            if hasattr(self._lcd_display, 'init'):
                if not self._lcd_display.init():
                    logger.warning("LCD display init returned False")
        except Exception as e:
            logger.warning(f"LCD display init error: {e}")
            # Non-fatal - can run without LCD

        return success

    def _init_audio(self) -> bool:
        """Initialize audio system."""
        try:
            self._audio_engine = get_audio_engine()
            if self._audio_engine.init():
                logger.info("Audio engine initialized")
                return True
            else:
                logger.warning("Audio engine init returned False")
                return False
        except Exception as e:
            logger.warning(f"Audio init error: {e}")
            return False

    def _init_pygame(self) -> bool:
        """Initialize pygame for event handling."""
        try:
            import os

            # Set kmsdrm video driver for Pi hardware mode BEFORE pygame import
            # This is required for direct HDMI output without X11/Wayland
            if not os.environ.get("DISPLAY") and os.path.exists("/dev/dri"):
                os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
                logger.info("Using kmsdrm video driver for Pi hardware")

            pygame = _get_pygame()
            pygame.init()
            self._clock = pygame.time.Clock()
            logger.info("Pygame initialized for hardware runner")
            return True
        except Exception as e:
            logger.error(f"Pygame init error: {e}")
            return False

    def init(self) -> bool:
        """Initialize all hardware."""
        if self._initialized:
            return True

        logger.info("Initializing hardware...")

        # Initialize pygame first (needed for HDMI display)
        if not self._init_pygame():
            return False

        # Initialize displays
        if not self._init_displays():
            logger.error("Failed to initialize displays")
            return False

        # Initialize audio (non-fatal if fails)
        self._init_audio()

        self._initialized = True
        logger.info("Hardware initialized successfully")
        return True

    def _handle_events(self) -> None:
        """Process pygame events (keyboard fallback for GPIO)."""
        pygame = _get_pygame()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

    def _handle_keydown(self, event) -> None:
        """Handle key press events."""
        pygame = _get_pygame()
        key = event.key

        # System keys
        if key == pygame.K_ESCAPE or key == pygame.K_q:
            self._running = False
        elif key == pygame.K_r:
            # Reboot to idle
            self.event_bus.emit(Event(EventType.REBOOT, source="keyboard"))
        elif key == pygame.K_BACKSPACE:
            # Go back
            self.event_bus.emit(Event(EventType.BACK, source="keyboard"))

        # Center button (SPACE or RETURN)
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self.event_bus.emit(Event(EventType.BUTTON_PRESS, source="center"))

        # Arcade buttons
        elif key == pygame.K_LEFT:
            self.event_bus.emit(Event(EventType.ARCADE_LEFT, source="arcade"))
        elif key == pygame.K_RIGHT:
            self.event_bus.emit(Event(EventType.ARCADE_RIGHT, source="arcade"))

        # Keypad (0-9, *, #)
        elif key in range(pygame.K_0, pygame.K_9 + 1):
            char = chr(key)
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": char},
                source="keypad"
            ))
        elif key == pygame.K_KP0:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "0"},
                source="keypad"
            ))
        elif key in range(pygame.K_KP1, pygame.K_KP9 + 1):
            char = str(key - pygame.K_KP1 + 1)
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": char},
                source="keypad"
            ))
        elif key == pygame.K_ASTERISK or key == pygame.K_KP_MULTIPLY:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "*"},
                source="keypad"
            ))
        elif key == pygame.K_HASH:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "#"},
                source="keypad"
            ))

    def _handle_keyup(self, event) -> None:
        """Handle key release events."""
        pygame = _get_pygame()
        key = event.key

        if key in (pygame.K_SPACE, pygame.K_RETURN):
            self.event_bus.emit(Event(EventType.BUTTON_RELEASE, source="center"))

    def _update_displays(self) -> None:
        """Update all displays from their buffers."""
        # Main display
        if self._main_display:
            self._main_display.show()

        # Ticker display
        if self._ticker_display:
            self._ticker_display.show()

        # LCD doesn't need explicit update (writes are immediate)

    async def run(self) -> None:
        """Main hardware loop."""
        if not self._initialized:
            if not self.init():
                logger.error("Hardware initialization failed")
                return

        self._running = True
        logger.info("Hardware runner started")

        # Play startup sound
        if self._audio_engine:
            self._audio_engine.play_startup()

        while self._running:
            # Handle events
            self._handle_events()

            # Emit tick event
            if self._clock:
                delta = self._clock.get_time() / 1000.0
                self.event_bus.emit(Event(
                    EventType.TICK,
                    data={"delta": delta, "frame": self._frame_count}
                ))

            # Process event queue
            await self.event_bus.process_queue()

            # Update displays
            self._update_displays()

            # Frame timing
            if self._clock:
                self._clock.tick(self.config.fps)

            self._frame_count += 1

            # Yield to other tasks
            await asyncio.sleep(0)

        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up hardware resources."""
        logger.info("Cleaning up hardware...")

        # Cleanup displays
        if self._main_display:
            if hasattr(self._main_display, 'cleanup'):
                self._main_display.cleanup()

        if self._ticker_display:
            if hasattr(self._ticker_display, 'cleanup'):
                self._ticker_display.cleanup()

        if self._lcd_display:
            if hasattr(self._lcd_display, 'cleanup'):
                self._lcd_display.cleanup()

        # Cleanup audio
        if self._audio_engine:
            self._audio_engine.cleanup()

        # Cleanup pygame
        pygame = _get_pygame()
        pygame.quit()

        logger.info("Hardware cleanup complete")

    def stop(self) -> None:
        """Stop the hardware runner."""
        self._running = False

    # === Display Access ===

    @property
    def main_display(self):
        """Get main display for drawing."""
        return self._main_display

    @property
    def ticker_display(self):
        """Get ticker display for drawing."""
        return self._ticker_display

    @property
    def lcd_display(self):
        """Get LCD display for text output."""
        return self._lcd_display

    @property
    def audio_engine(self):
        """Get audio engine."""
        return self._audio_engine
