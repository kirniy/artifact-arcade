"""
Simulator entry point - Fully integrated with mode system.

Runs the ARTIFACT arcade machine in a desktop pygame window.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from artifact.simulator.window import SimulatorWindow, WindowConfig
from artifact.core.state import StateMachine
from artifact.core.events import EventBus, Event, EventType
from artifact.graphics.renderer import Renderer
from artifact.animation.engine import AnimationEngine
from artifact.modes.manager import ModeManager
# Active modes only (in display order)
from artifact.modes.roast import RoastMeMode             # ПРОЖАРКА (first!)
from artifact.modes.bad_santa import BadSantaMode        # ПЛОХОЙ САНТА (18+)
# from artifact.modes.y2k import Y2KMode                 # НУЛЕВЫЕ - HIDDEN
# from artifact.modes.sorting_hat import SortingHatMode  # ШЛЯПА - HIDDEN
from artifact.modes.fortune import FortuneMode           # ГАДАЛКА
from artifact.modes.ai_prophet import AIProphetMode      # ПРОРОК
from artifact.modes.photobooth import PhotoboothMode     # ФОТОБУДКА
from artifact.modes.guess_me import GuessMeMode          # КТО Я?
from artifact.modes.squid_game import SquidGameMode      # КАЛЬМАР
from artifact.modes.quiz import QuizMode                 # КВИЗ
from artifact.modes.tower_stack import TowerStackMode    # БАШНЯ
from artifact.modes.brick_breaker import BrickBreakerMode  # КИРПИЧИ
from artifact.modes.video import VideoMode               # ВИДЕО
from artifact.modes.gallery import GalleryMode, start_gallery_preloader           # ГАЛЕРЕЯ
from artifact.audio.engine import AudioEngine, get_audio_engine
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


def is_real_printer_enabled() -> bool:
    """Check if real printer is enabled (checked at runtime, not import time).

    Checks both environment variable AND .simulator-config file directly.
    """
    # First check env var
    val = os.environ.get("ARTIFACT_REAL_PRINTER", "")

    # If not in env, try reading config file directly
    if not val:
        config_path = Path(__file__).parent.parent.parent.parent / ".simulator-config"
        if config_path.exists():
            try:
                content = config_path.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("ARTIFACT_REAL_PRINTER="):
                        val = line.split("=", 1)[1].strip()
                        break
            except Exception:
                pass

    return val == "1"


def setup_logging() -> None:
    """Configure logging for simulator with file output."""
    from pathlib import Path

    # Log file in project root
    log_file = Path(__file__).parent.parent.parent.parent / "simulator.log"

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # File handler - truncate on each run for fresh logs
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Root logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from some modules
    logging.getLogger("artifact.animation").setLevel(logging.INFO)
    logging.getLogger("artifact.graphics").setLevel(logging.INFO)

    logging.info(f"Logging to file: {log_file}")


class ArtifactSimulator:
    """Main simulator application integrating all systems."""

    def __init__(self):
        # Core systems
        self.state_machine = StateMachine()
        self.event_bus = EventBus()
        self.renderer = Renderer()
        self.animation_engine = AnimationEngine()

        # Audio system - synthwave arcade sounds!
        self.audio = get_audio_engine()
        self.audio.init()

        # Start shared camera service (always-on for instant frames)
        camera_service.start()
        logger.info(f"Camera service: running={camera_service.is_running}, has_camera={camera_service.has_camera}")

        # Window
        self.window_config = WindowConfig(
            width=1280,
            height=720,
            title="ARTIFACT Simulator",
            fps=60
        )
        self.window = SimulatorWindow(
            config=self.window_config,
            state_machine=self.state_machine,
            event_bus=self.event_bus
        )

        # Mode system
        self.mode_manager = ModeManager(
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            renderer=self.renderer,
            animation_engine=self.animation_engine,
            theme="mystical"
        )

        # Register available modes (excluding AI Prophet for now - needs camera)
        self._register_modes()

        # Start gallery preloader for instant photo loading
        start_gallery_preloader()

        # Real printer support (for testing from Mac)
        self._real_printer = None
        if is_real_printer_enabled():
            self._setup_real_printer()

        # Wire up event handlers
        self._setup_event_handlers()

        logger.info("ArtifactSimulator initialized")

    def _setup_real_printer(self) -> None:
        """Setup real USB printer for testing."""
        try:
            from artifact.hardware.printer import IP802Printer, auto_detect_label_printer

            port = auto_detect_label_printer()
            if port:
                self._real_printer = IP802Printer(port=port)
                # Connect asynchronously later
                logger.info(f"Real printer configured: {port}")
            else:
                logger.warning("Real printer not found, using preview only")
        except Exception as e:
            logger.error(f"Failed to setup real printer: {e}")

    def _register_modes(self) -> None:
        """Register game modes in display order."""
        import os
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Check for API key
        has_api_key = bool(os.environ.get("GEMINI_API_KEY"))

        # Register modes in order: Roast -> Photobooth -> Quiz -> rest
        # ПРОЖАРКА - Roast mode (FIRST!)
        self.mode_manager.register_mode(RoastMeMode)
        logger.info("🔥 ROAST MODE registered as #1")

        # ФОТОБУДКА - Photo booth (SECOND)
        self.mode_manager.register_mode(PhotoboothMode)

        # КВИЗ - Quiz (THIRD)
        self.mode_manager.register_mode(QuizMode)

        # Time-based mode activation (Bad Santa only on Jan 9 after 5pm Moscow)
        moscow_tz = ZoneInfo('Europe/Moscow')
        now = datetime.now(moscow_tz)
        bad_santa_active = (now.month == 1 and now.day == 9 and now.hour >= 17)

        if bad_santa_active and has_api_key:
            self.mode_manager.register_mode(BadSantaMode)
            logger.info("🎅 BAD SANTA MODE ACTIVE! (Jan 9 after 5pm Moscow)")

        # Y2K and Sorting Hat are HIDDEN for now
        # if has_api_key:
        #     self.mode_manager.register_mode(Y2KMode)
        #     self.mode_manager.register_mode(SortingHatMode)

        if not has_api_key:
            logger.warning("AI modes disabled (no GEMINI_API_KEY)")

        # ГАДАЛКА - Fortune teller
        self.mode_manager.register_mode(FortuneMode)

        # ПРОРОК - AI Prophet (requires API key)
        if has_api_key:
            self.mode_manager.register_mode(AIProphetMode)
            logger.info("AI Prophet mode enabled (API key found)")

        # КТО Я? - AI guessing "Who Am I?"
        self.mode_manager.register_mode(GuessMeMode)

        # КАЛЬМАР - Squid game (red light/green light)
        self.mode_manager.register_mode(SquidGameMode)

        # БАШНЯ - Tower stack
        self.mode_manager.register_mode(TowerStackMode)

        # КИРПИЧИ - Brick breaker
        self.mode_manager.register_mode(BrickBreakerMode)

        # ВИДЕО - Video player
        self.mode_manager.register_mode(VideoMode)

        # ГАЛЕРЕЯ - Photo gallery slideshow
        self.mode_manager.register_mode(GalleryMode)

        logger.info(f"Registered {len(self.mode_manager._registered_modes)} modes")

    def _setup_event_handlers(self) -> None:
        """Set up event routing between window and mode manager."""
        # ModeManager already subscribes to input events internally
        # We just need tick for updates
        self.event_bus.subscribe(EventType.TICK, self._on_tick)

        # Audio event handlers - play sounds on UI events
        self.event_bus.subscribe(EventType.BUTTON_PRESS, self._on_button_sound)
        self.event_bus.subscribe(EventType.ARCADE_LEFT, self._on_nav_sound)
        self.event_bus.subscribe(EventType.ARCADE_RIGHT, self._on_nav_sound)
        self.event_bus.subscribe(EventType.BACK, self._on_back_sound)

        # Printer preview - show receipt when printing starts
        self.event_bus.subscribe(EventType.PRINT_START, self._on_print_start)

    def _on_button_sound(self, event: Event) -> None:
        """Play button press sound."""
        self.audio.play_ui_confirm()

    def _on_nav_sound(self, event: Event) -> None:
        """Play navigation sound."""
        self.audio.play_ui_move()

    def _on_back_sound(self, event: Event) -> None:
        """Play back sound."""
        self.audio.play_ui_back()

    def _on_print_start(self, event: Event) -> None:
        """Handle print start - show printer preview with receipt content."""
        print_data = event.data if event.data else {}
        logger.info(f"Print started with data: {print_data.get('type', 'unknown')}")

        # Trigger the printer preview in the simulator window
        self.window.trigger_print(print_data)

        # Also print to real printer if enabled
        if self._real_printer and is_real_printer_enabled():
            asyncio.create_task(self._print_to_real_printer(print_data))

        # Play printer sound effect
        self.audio.play_reward()

    async def _print_to_real_printer(self, print_data: dict) -> None:
        """Print to real USB printer."""
        try:
            # Connect if not connected
            if not self._real_printer.is_connected:
                await self._real_printer.connect()

            # Generate receipt using label layout engine
            from artifact.printing.label_receipt import LabelReceiptGenerator
            from artifact.printing.label_layout import LabelLayoutEngine

            mode_type = print_data.get('type', 'unknown')
            generator = LabelReceiptGenerator()
            receipt = generator.generate_receipt(mode_type, print_data)

            # Render to TSPL commands
            engine = LabelLayoutEngine()
            tspl_commands = engine.render(receipt.layout, protocol="tspl")

            # Send to printer
            await self._real_printer.print_raw(tspl_commands)
            logger.info(f"Real printer: sent {len(tspl_commands)} bytes")

        except Exception as e:
            logger.error(f"Real printer error: {e}")

    def _on_tick(self, event: Event) -> None:
        """Handle frame tick - update and render."""
        delta = event.data.get("delta", 0.016)  # Default 60fps
        delta_ms = delta * 1000

        # Update mode manager
        self.mode_manager.update(delta_ms)

        # Update animation engine
        self.animation_engine.update(delta_ms)

        # Render to window buffers
        self._render_to_window()

    def _render_to_window(self) -> None:
        """Render mode content to simulator window displays."""
        import numpy as np

        # Get display buffers from window
        main_buffer = self.window.main_display._buffer
        ticker_buffer = self.window.ticker_display._buffer

        # Let mode manager render
        self.mode_manager.render_main(main_buffer)
        self.mode_manager.render_ticker(ticker_buffer)

        # Update LCD text
        lcd_text = self.mode_manager.get_lcd_text()
        self.window.lcd_display.set_text(lcd_text)

    async def run(self) -> None:
        """Run the simulator."""
        logger.info("Starting ARTIFACT Simulator...")

        # Play startup fanfare!
        self.audio.play_startup()

        # Start idle ambient loop
        self.audio.start_idle_ambient()

        # Run the window (main loop)
        await self.window.run()

        # Cleanup
        if self._real_printer and self._real_printer.is_connected:
            await self._real_printer.disconnect()
        camera_service.stop()
        self.audio.cleanup()


async def run() -> None:
    """Main entry point."""
    simulator = ArtifactSimulator()
    await simulator.run()


def main() -> None:
    """Main entry point for simulator."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("ARTIFACT Simulator Starting")
    logger.info("=" * 50)
    logger.info("")
    logger.info("Controls:")
    logger.info("  SPACE/ENTER  - Center button (start/confirm)")
    logger.info("  LEFT/RIGHT   - Arcade buttons (select/answer)")
    logger.info("  0-9, *, #    - Keypad input")
    logger.info("  R            - Restart")
    logger.info("")
    logger.info("System (Mac-friendly):")
    logger.info("  F  - Toggle fullscreen")
    logger.info("  D  - Toggle debug panel")
    logger.info("  L  - Toggle log viewer")
    logger.info("  P  - Toggle printer preview")
    logger.info("  T  - Toggle print test panel (load & print images)")
    logger.info("  S  - Screenshot")
    logger.info("  Q  - Quit")
    logger.info("")
    # Always log printer status for debugging
    printer_env = os.environ.get("ARTIFACT_REAL_PRINTER", "")
    config_path = Path(__file__).parent.parent.parent.parent / ".simulator-config"
    logger.info(f"Printer config: env={printer_env!r}, config_file={config_path.exists()}")
    if is_real_printer_enabled():
        logger.info("** REAL PRINTER MODE ENABLED **")
        logger.info("   Print events will be sent to USB printer")
    else:
        logger.info("Real printer DISABLED (set ARTIFACT_REAL_PRINTER=1 in .simulator-config)")
    logger.info("")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    except Exception as e:
        logger.exception(f"Simulator error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
