"""
Hardware runner for ARTIFACT on Raspberry Pi.

Manages real hardware: HDMI display (via T50), WS2812B LEDs,
I2C LCD, GPIO inputs, camera, and thermal printer.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from ..core.state import StateMachine
from ..core.events import EventBus, EventType, Event
from ..audio.engine import get_audio_engine
from ..utils.usb_button import turn_on_button_led

logger = logging.getLogger(__name__)

# Control file paths (shared with Telegram bot)
CONTROL_FILE = Path(os.environ.get(
    "ARCADE_CONTROL_FILE",
    "/home/kirniy/modular-arcade/data/control.json"
))
STATUS_FILE = Path(os.environ.get(
    "ARCADE_STATUS_FILE",
    "/home/kirniy/modular-arcade/data/status.json"
))

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
    lcd_rows: int = 1

    # GPIO settings
    ws2812b_gpio: int = 21  # Not 18 to avoid audio conflict
    ws2812b_brightness: int = 128

    # Arcade button GPIO pins (directly wired, active LOW with pull-up)
    # Buttons connect GPIO to GND when pressed
    gpio_button_left: int = 17   # Pin 11 - LEFT arcade button
    gpio_button_right: int = 27  # Pin 13 - RIGHT arcade button

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

        # GPIO button state
        self._gpio_initialized = False
        self._gpio_left_button = None
        self._gpio_right_button = None
        self._left_button_was_pressed = False
        self._right_button_was_pressed = False

        # State
        self._running = False
        self._frame_count = 0
        self._clock = None
        self._initialized = False

        # Long-press shutdown tracking
        self._backspace_pressed_time: float | None = None
        self._shutdown_hold_duration = 3.0  # seconds to hold for shutdown

        # Use mock displays if hardware unavailable
        self._use_mocks = os.getenv("ARTIFACT_MOCK_HARDWARE", "false").lower() == "true"

        # Control file tracking
        self._last_control_check = 0.0
        self._control_check_interval = 0.1  # Check every 100ms
        self._last_status_write = 0.0
        self._status_write_interval = 1.0  # Write status every 1s
        self._current_mode = "idle"
        self._current_scene = 0

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
        """Initialize full audio system with all chiptune sounds and music.

        Sets up Pi 3.5mm jack (hw:2,0) and loads the complete AudioEngine
        with procedural synthwave sounds and music loops.
        """
        import os
        import subprocess

        try:
            pygame = _get_pygame()

            # Load bcm2835 module for 3.5mm jack
            subprocess.run(['modprobe', 'snd-bcm2835'], capture_output=True)

            # Use 3.5mm headphone jack (card 2)
            os.environ['AUDIODEV'] = 'hw:2,0'
            os.environ['SDL_AUDIODRIVER'] = 'alsa'

            # Quit existing mixer (initialized by pygame.init()) and reinitialize
            # with correct audio device settings
            try:
                pygame.mixer.quit()
            except Exception:
                pass

            # Pre-init mixer with Pi audio settings before reinitializing
            pygame.mixer.pre_init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=4096  # Larger buffer for Pi stability
            )
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)

            logger.info(f"Mixer reinitialized for hw:2,0 (3.5mm jack)")

            # Get and initialize the full audio engine (skip its mixer init)
            self._audio_engine = get_audio_engine()
            # Mark as initialized since we already set up the mixer
            self._audio_engine._initialized = True
            self._audio_engine._generate_all_sounds()

            logger.info("Audio initialized: 3.5mm jack (hw:2,0) with full AudioEngine")
            self._audio_enabled = True
            return True

        except Exception as e:
            logger.warning(f"Audio init failed: {e}")
            self._audio_enabled = False
            self._audio_engine = None
            return False

    def _init_gpio_buttons(self) -> bool:
        """Initialize GPIO arcade buttons using gpiozero.

        LEFT button on GPIO 17 (Pin 11)
        RIGHT button on GPIO 27 (Pin 13)

        Buttons are wired active LOW: GPIO to button to GND.
        Internal pull-up resistors are enabled.
        """
        try:
            from gpiozero import Button

            # LEFT button - GPIO 17 with internal pull-up
            self._gpio_left_button = Button(
                self.config.gpio_button_left,
                pull_up=True,  # Enable internal pull-up resistor
                bounce_time=0.05  # 50ms debounce
            )

            # RIGHT button - GPIO 27 with internal pull-up
            self._gpio_right_button = Button(
                self.config.gpio_button_right,
                pull_up=True,
                bounce_time=0.05
            )

            self._gpio_initialized = True
            logger.info(
                f"GPIO buttons initialized: LEFT=GPIO{self.config.gpio_button_left}, "
                f"RIGHT=GPIO{self.config.gpio_button_right}"
            )
            return True

        except ImportError:
            logger.warning("gpiozero not available - GPIO buttons disabled")
            return False
        except Exception as e:
            logger.warning(f"GPIO button init failed: {e}")
            return False

    def _poll_gpio_buttons(self) -> None:
        """Poll GPIO buttons and emit events on state change.

        Uses edge detection to emit events only on press (not continuous).
        """
        if not self._gpio_initialized:
            return

        # Check LEFT button
        if self._gpio_left_button:
            is_pressed = self._gpio_left_button.is_pressed
            if is_pressed and not self._left_button_was_pressed:
                # Button just pressed
                self.play_sound('click')
                self.event_bus.emit(Event(EventType.ARCADE_LEFT, source="gpio"))
                logger.debug("GPIO LEFT button pressed")
            self._left_button_was_pressed = is_pressed

        # Check RIGHT button
        if self._gpio_right_button:
            is_pressed = self._gpio_right_button.is_pressed
            if is_pressed and not self._right_button_was_pressed:
                # Button just pressed
                self.play_sound('click')
                self.event_bus.emit(Event(EventType.ARCADE_RIGHT, source="gpio"))
                logger.debug("GPIO RIGHT button pressed")
            self._right_button_was_pressed = is_pressed

    def _read_control_commands(self) -> None:
        """Read and process control commands from Telegram bot."""
        now = time.time()
        if now - self._last_control_check < self._control_check_interval:
            return
        self._last_control_check = now

        if not CONTROL_FILE.exists():
            return

        try:
            with open(CONTROL_FILE, 'r') as f:
                data = json.load(f)

            # Remove file after reading (one-shot commands)
            CONTROL_FILE.unlink()

            command = data.get("command")
            timestamp = data.get("timestamp", 0)

            # Ignore stale commands (older than 5 seconds)
            if now - timestamp > 5:
                logger.debug(f"Ignoring stale command: {command}")
                return

            logger.info(f"Processing control command: {command}")

            if command == "volume":
                level = data.get("level", 1.0)
                if self._audio_engine:
                    self._audio_engine.set_volume(level)
                    logger.info(f"Volume set to {level}")

            elif command == "mute":
                if self._audio_engine:
                    self._audio_engine.mute()
                    logger.info("Audio muted")

            elif command == "unmute":
                if self._audio_engine:
                    self._audio_engine.unmute()
                    logger.info("Audio unmuted")

            elif command == "idle_scene":
                scene = data.get("scene", 0)
                self._current_scene = scene
                self.event_bus.emit(Event(
                    EventType.IDLE_SCENE_CHANGE,
                    data={"scene": scene},
                    source="remote"
                ))
                logger.info(f"Idle scene set to {scene}")

            elif command == "idle_next":
                self.event_bus.emit(Event(
                    EventType.IDLE_SCENE_NEXT,
                    source="remote"
                ))
                logger.info("Next idle scene")

            elif command == "idle_prev":
                self.event_bus.emit(Event(
                    EventType.IDLE_SCENE_PREV,
                    source="remote"
                ))
                logger.info("Previous idle scene")

            elif command == "start_mode":
                mode = data.get("mode", "fortune")
                self._current_mode = mode
                self.event_bus.emit(Event(
                    EventType.MODE_SELECT,
                    data={"mode": mode},
                    source="remote"
                ))
                logger.info(f"Starting mode: {mode}")

            elif command == "button":
                button = data.get("button", "start")
                # Map button names to events
                button_map = {
                    "start": (EventType.BUTTON_PRESS, {"button": "enter"}),
                    "left": (EventType.ARCADE_LEFT, {}),
                    "right": (EventType.ARCADE_RIGHT, {}),
                    "up": (EventType.ARCADE_UP, {}),
                    "down": (EventType.ARCADE_DOWN, {}),
                    "back": (EventType.BACK, {}),
                }
                if button in button_map:
                    event_type, event_data = button_map[button]
                    self.play_sound('click')
                    self.event_bus.emit(Event(event_type, data=event_data, source="remote"))
                    logger.info(f"Button press: {button}")

            elif command == "reboot":
                logger.info("Reboot requested via remote")
                self.play_sound('error')
                self.event_bus.emit(Event(EventType.REBOOT, source="remote"))

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid control file JSON: {e}")
        except Exception as e:
            logger.warning(f"Error reading control file: {e}")

    def _write_status(self) -> None:
        """Write current status for Telegram bot to read."""
        now = time.time()
        if now - self._last_status_write < self._status_write_interval:
            return
        self._last_status_write = now

        try:
            # Ensure data directory exists
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

            status = {
                "mode": self._current_mode,
                "scene": self._current_scene,
                "volume": self._audio_engine.get_volume() if self._audio_engine else 1.0,
                "muted": self._audio_engine.is_muted() if self._audio_engine else False,
                "running": self._running,
                "frame": self._frame_count,
                "timestamp": now,
            }

            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f)

        except Exception as e:
            logger.debug(f"Error writing status file: {e}")

    def set_current_mode(self, mode: str) -> None:
        """Update current mode (called by ModeManager)."""
        self._current_mode = mode

    def set_current_scene(self, scene: int) -> None:
        """Update current idle scene index."""
        self._current_scene = scene

    def play_sound(self, name: str) -> None:
        """Play a UI sound effect using the full AudioEngine."""
        if not hasattr(self, '_audio_enabled') or not self._audio_enabled:
            return
        if not self._audio_engine:
            return

        try:
            # Map simple names to AudioEngine methods
            sound_map = {
                'click': self._audio_engine.play_ui_click,
                'confirm': self._audio_engine.play_ui_confirm,
                'error': self._audio_engine.play_ui_error,
                'back': self._audio_engine.play_ui_back,
                'move': self._audio_engine.play_ui_move,
                'success': self._audio_engine.play_success,
                'failure': self._audio_engine.play_failure,
                'countdown_tick': self._audio_engine.play_countdown_tick,
                'countdown_go': self._audio_engine.play_countdown_go,
                'wheel_tick': self._audio_engine.play_wheel_tick,
                'wheel_stop': self._audio_engine.play_wheel_stop,
                'jackpot': self._audio_engine.play_jackpot,
                'shutter': self._audio_engine.play_camera_shutter,
                'print': self._audio_engine.play_print,
                'quiz_correct': self._audio_engine.play_quiz_correct,
                'quiz_wrong': self._audio_engine.play_quiz_wrong,
                'roulette_spin': self._audio_engine.play_roulette_spin,
                'startup': self._audio_engine.play_startup,
                'transition': self._audio_engine.play_transition,
            }

            if name in sound_map:
                sound_map[name]()
            else:
                # Try direct play for any other sound
                self._audio_engine.play(name)
        except Exception as e:
            logger.debug(f"Sound play error: {e}")

    def play_music(self, track_name: str) -> None:
        """Play a music track (looping).

        Args:
            track_name: Name of the track (e.g., "idle", "menu", "fortune")
        """
        if self._audio_engine and self._audio_enabled:
            try:
                self._audio_engine.play_music(track_name)
            except Exception as e:
                logger.debug(f"Music play error: {e}")

    def stop_music(self) -> None:
        """Stop currently playing music."""
        if self._audio_engine:
            try:
                self._audio_engine.stop_music()
            except Exception:
                pass

    def start_idle_ambient(self) -> None:
        """Start idle ambient music and sounds."""
        if self._audio_engine and self._audio_enabled:
            try:
                self._audio_engine.start_idle_ambient()
                self._audio_engine.play_music("idle")
            except Exception as e:
                logger.debug(f"Idle ambient error: {e}")

    def _init_pygame(self) -> bool:
        """Initialize pygame for event handling."""
        try:
            # NOTE: Do NOT set SDL_VIDEODRIVER=kmsdrm explicitly on Debian Trixie!
            # Let pygame auto-detect the driver - explicit setting breaks initialization.
            pygame = _get_pygame()
            pygame.init()
            self._clock = pygame.time.Clock()
            logger.info(f"Pygame initialized (driver: {pygame.display.get_driver()})")
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

        # Initialize GPIO arcade buttons (non-fatal if fails)
        self._init_gpio_buttons()

        self._initialized = True
        logger.info("Hardware initialized successfully")
        return True

    def _handle_events(self) -> None:
        """Process pygame events (keyboard fallback for GPIO)."""
        import time
        pygame = _get_pygame()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

        # Check for long-press shutdown (Backspace held 3 seconds)
        if self._backspace_pressed_time is not None:
            held_duration = time.time() - self._backspace_pressed_time
            if held_duration >= self._shutdown_hold_duration:
                logger.warning("Backspace held 3s - initiating shutdown!")
                self._shutdown_system()

    def _handle_keydown(self, event) -> None:
        """Handle key press events."""
        pygame = _get_pygame()
        key = event.key

        # System keys
        if key == pygame.K_ESCAPE or key == pygame.K_q:
            self._running = False
        elif key == pygame.K_r:
            # Reboot to idle
            self.play_sound('error')
            self.event_bus.emit(Event(EventType.REBOOT, source="keyboard"))
        elif key == pygame.K_BACKSPACE:
            # Start tracking for long-press shutdown
            import time
            if self._backspace_pressed_time is None:
                self._backspace_pressed_time = time.time()
                logger.debug("Backspace pressed - hold 3s to shutdown")

        # Center button (SPACE or RETURN)
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self.play_sound('confirm')
            self.event_bus.emit(Event(EventType.BUTTON_PRESS, data={"button": "enter"}, source="center"))

        # Arcade buttons (regular arrows)
        elif key == pygame.K_LEFT:
            self.play_sound('click')
            self.event_bus.emit(Event(EventType.ARCADE_LEFT, source="arcade"))
        elif key == pygame.K_RIGHT:
            self.play_sound('click')
            self.event_bus.emit(Event(EventType.ARCADE_RIGHT, source="arcade"))
        elif key == pygame.K_UP:
            self.play_sound('click')
            self.event_bus.emit(Event(EventType.ARCADE_UP, source="arcade"))
        elif key == pygame.K_DOWN:
            self.play_sound('click')
            self.event_bus.emit(Event(EventType.ARCADE_DOWN, source="arcade"))

        # Numpad Enter - works as confirm button
        elif key == pygame.K_KP_ENTER:
            self.play_sound('confirm')
            self.event_bus.emit(Event(EventType.BUTTON_PRESS, data={"button": "enter"}, source="center"))

        # Numpad 4/6 - work as BOTH navigation AND digits
        # (mode decides which event to handle)
        elif key == pygame.K_KP4:
            self.event_bus.emit(Event(EventType.ARCADE_LEFT, source="numpad"))
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "4"},
                source="keypad"
            ))
        elif key == pygame.K_KP6:
            self.event_bus.emit(Event(EventType.ARCADE_RIGHT, source="numpad"))
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "6"},
                source="keypad"
            ))
        # Numpad 8/2 - work as up/down navigation AND digits
        elif key == pygame.K_KP8:
            self.event_bus.emit(Event(EventType.ARCADE_UP, source="numpad"))
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "8"},
                source="keypad"
            ))
        elif key == pygame.K_KP2:
            self.event_bus.emit(Event(EventType.ARCADE_DOWN, source="numpad"))
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "2"},
                source="keypad"
            ))

        # Keypad (0-9, *, #) - regular number row
        elif key in range(pygame.K_0, pygame.K_9 + 1):
            char = chr(key)
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": char},
                source="keypad"
            ))
        # Numpad digits (except 2,4,6,8 which are handled above)
        elif key == pygame.K_KP0:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "0"},
                source="keypad"
            ))
        elif key == pygame.K_KP1:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "1"},
                source="keypad"
            ))
        elif key == pygame.K_KP3:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "3"},
                source="keypad"
            ))
        elif key == pygame.K_KP5:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "5"},
                source="keypad"
            ))
        elif key == pygame.K_KP7:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "7"},
                source="keypad"
            ))
        elif key == pygame.K_KP9:
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "9"},
                source="keypad"
            ))
        elif key == pygame.K_ASTERISK or key == pygame.K_KP_MULTIPLY:
            # Toggle mute with asterisk key
            if self._audio_engine:
                muted = self._audio_engine.toggle_mute()
                logger.info(f"Audio {'muted' if muted else 'unmuted'}")
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "*"},
                source="keypad"
            ))
        elif key == pygame.K_HASH or key == pygame.K_KP_PLUS:
            # Use numpad + as # since numpad doesn't have #
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT,
                data={"key": "#"},
                source="keypad"
            ))

    def _handle_keyup(self, event) -> None:
        """Handle key release events."""
        import time
        pygame = _get_pygame()
        key = event.key

        if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.event_bus.emit(Event(EventType.BUTTON_RELEASE, source="center"))

        elif key == pygame.K_BACKSPACE:
            # If released before 3s, emit BACK event (go back/cancel)
            if self._backspace_pressed_time is not None:
                held_duration = time.time() - self._backspace_pressed_time
                self._backspace_pressed_time = None
                if held_duration < self._shutdown_hold_duration:
                    self.event_bus.emit(Event(EventType.BACK, source="keyboard"))

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

        # Turn on USB button LED (keep it lit always)
        if turn_on_button_led():
            logger.info("USB button LED turned on")

        # Play startup sound and start idle music
        if self._audio_engine:
            self._audio_engine.play_startup()
            # Start idle ambient loop after a short delay for startup fanfare
            import time
            time.sleep(0.5)  # Let startup fanfare play briefly
            self.start_idle_ambient()

        while self._running:
            # Handle events from hardware
            self._handle_events()

            # Poll GPIO arcade buttons
            self._poll_gpio_buttons()

            # Handle remote control commands from Telegram bot
            self._read_control_commands()

            # Write status for Telegram bot
            self._write_status()

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

    def _shutdown_system(self) -> None:
        """Shutdown the Raspberry Pi (called on long Backspace press)."""
        import subprocess

        logger.warning("=== SYSTEM SHUTDOWN INITIATED ===")

        # Cleanup before shutdown
        self._running = False
        self._cleanup()

        # Clear the display before shutdown (show black)
        try:
            pygame = _get_pygame()
            if self._main_display:
                self._main_display.clear(0, 0, 0)
                self._main_display.show()
        except Exception:
            pass

        # Execute shutdown command
        try:
            logger.info("Executing: sudo shutdown now")
            subprocess.run(["sudo", "shutdown", "now"], check=False)
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            # If shutdown fails (e.g., not running as root), at least exit
            import sys
            sys.exit(0)

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
