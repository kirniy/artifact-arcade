"""
Main entry point for ARTIFACT application.

Automatically detects environment (simulator or hardware)
and launches the appropriate version.
"""

import asyncio
import logging
import sys
import threading
import time
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from artifact.core.state import StateMachine
from artifact.core.events import EventBus


def setup_logging(debug: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )


async def run_simulator() -> None:
    """Run the simulator version."""
    from artifact.simulator.window import SimulatorWindow, WindowConfig

    # Create shared components
    state_machine = StateMachine()
    event_bus = EventBus()

    # Create and run simulator
    config = WindowConfig()
    window = SimulatorWindow(
        config=config,
        state_machine=state_machine,
        event_bus=event_bus
    )

    await window.run()


async def run_hardware() -> None:
    """Run the hardware version (on Raspberry Pi)."""
    import os
    from artifact.hardware.runner import HardwareRunner, HardwareConfig
    from artifact.graphics.renderer import Renderer
    from artifact.animation.engine import AnimationEngine
    from artifact.modes.manager import ModeManager
    from artifact.core.events import Event, EventType
    from artifact.printing.manager import PrintManager
    from artifact.utils.camera_service import camera_service

    # Import curated game modes (same as simulator)
    from artifact.modes.roast import RoastMeMode             # ПРОЖАРКА (first!)
    from artifact.modes.bad_santa import BadSantaMode        # ПЛОХОЙ САНТА (18+)
    # from artifact.modes.y2k import Y2KMode                 # НУЛЕВЫЕ - HIDDEN
    # from artifact.modes.sorting_hat import SortingHatMode  # ШЛЯПА - HIDDEN
    from artifact.modes.fortune import FortuneMode           # ГАДАЛКА
    from artifact.modes.ai_prophet import AIProphetMode      # ПРОРОК
    from artifact.modes.photobooth import get_configured_photobooth_modes
    from artifact.modes.guess_me import GuessMeMode          # КТО Я?
    from artifact.modes.squid_game import SquidGameMode      # КАЛЬМАР
    from artifact.modes.quiz import QuizMode                 # КВИЗ
    from artifact.modes.tower_stack import TowerStackMode    # БАШНЯ
    from artifact.modes.brick_breaker import BrickBreakerMode  # КИРПИЧИ
    from artifact.modes.video import VideoMode               # ВИДЕО
    from artifact.modes.gallery import GalleryMode, start_gallery_preloader  # ГАЛЕРЕЯ

    logger = logging.getLogger(__name__)

    # Create shared components
    state_machine = StateMachine()
    event_bus = EventBus()
    renderer = Renderer()
    animation_engine = AnimationEngine()

    # Create hardware runner
    config = HardwareConfig()
    runner = HardwareRunner(
        config=config,
        state_machine=state_machine,
        event_bus=event_bus
    )

    # Create mode manager
    mode_manager = ModeManager(
        state_machine=state_machine,
        event_bus=event_bus,
        renderer=renderer,
        animation_engine=animation_engine,
        theme="mystical"
    )

    # Check for API key
    has_api_key = bool(os.environ.get("GEMINI_API_KEY"))

    # Register photobooth variants in order from config.
    for idx, photobooth_mode in enumerate(get_configured_photobooth_modes(), start=1):
        mode_manager.register_mode(photobooth_mode)
        logger.info("📸 %s registered as #%d", photobooth_mode.name.upper(), idx)

    # ПРОЖАРКА - Roast mode (DISABLED for BOILING ROOM)
    # mode_manager.register_mode(RoastMeMode)
    # logger.info("🔥 ROAST MODE registered as #2")

    # КВИЗ - Quiz (DISABLED for BOILING ROOM)
    # mode_manager.register_mode(QuizMode)

    # Time-based mode activation (Bad Santa only on Jan 9 after 5pm Moscow)
    # TEMPORARILY DISABLED - ONLY PHOTOBOOTH + ROAST FOR TODAY
    # from datetime import datetime
    # from zoneinfo import ZoneInfo
    # moscow_tz = ZoneInfo('Europe/Moscow')
    # now = datetime.now(moscow_tz)
    # bad_santa_active = (now.month == 1 and now.day == 9 and now.hour >= 17)
    #
    # if bad_santa_active and has_api_key:
    #     mode_manager.register_mode(BadSantaMode)
    #     logger.info("🎅 BAD SANTA MODE ACTIVE! (Jan 9 after 5pm Moscow)")

    # Y2K and Sorting Hat are HIDDEN for now
    # if has_api_key:
    #     mode_manager.register_mode(Y2KMode)
    #     mode_manager.register_mode(SortingHatMode)

    if not has_api_key:
        logger.warning("AI modes disabled (no GEMINI_API_KEY)")

    # ====== TEMPORARILY DISABLED - ONLY PHOTOBOOTH + ROAST FOR TODAY ======
    # ГАДАЛКА - Fortune teller (DISABLED)
    # mode_manager.register_mode(FortuneMode)

    # ПРОРОК - AI Prophet (requires API key) (DISABLED)
    # if has_api_key:
    #     mode_manager.register_mode(AIProphetMode)
    #     logger.info("AI Prophet mode enabled (API key found)")

    # КТО Я? - AI guessing "Who Am I?" (DISABLED for BOILING ROOM)
    # mode_manager.register_mode(GuessMeMode)

    # КАЛЬМАР - Squid game (red light/green light) (DISABLED for BOILING ROOM)
    # mode_manager.register_mode(SquidGameMode)

    # БАШНЯ - Tower stack (DISABLED)
    # mode_manager.register_mode(TowerStackMode)

    # КИРПИЧИ - Brick breaker (DISABLED)
    # mode_manager.register_mode(BrickBreakerMode)

    # ВИДЕО - Video player (DISABLED)
    # mode_manager.register_mode(VideoMode)

    # ГАЛЕРЕЯ - Photo gallery slideshow (DISABLED)
    # mode_manager.register_mode(GalleryMode)
    # ======================================================================

    logger.info(f"Registered {len(mode_manager._registered_modes)} modes")

    if os.getenv("ARTIFACT_UPLOAD_RETRY_IN_PROCESS", "").lower() in {"1", "true", "yes", "on"}:
        from artifact.utils.s3_upload import retry_pending_uploads

        def retry_spooled_uploads() -> None:
            while True:
                try:
                    summary = retry_pending_uploads(limit=100)
                    if summary["retried"] or summary["failed"]:
                        logger.info("Pending upload retry pass: %s", summary)
                except Exception:
                    logger.exception("Pending upload retry pass crashed")
                time.sleep(60)

        threading.Thread(target=retry_spooled_uploads, daemon=True).start()
    else:
        logger.info("In-process upload retry disabled; artifact-upload-spool service owns spool draining")

    # Initialize hardware
    if not runner.init():
        logger.error("Hardware initialization failed")
        return

    # Start shared camera service (always-on for instant frames)
    camera_service.start()
    logger.info(f"Camera service: running={camera_service.is_running}")

    # Start gallery preloader for instant photo loading
    # DISABLED: Blocks startup with network requests
    # start_gallery_preloader()

    # Initialize printer manager.
    # RP80 is auto-selected when present for photobooth roll prints.
    # Set ARTIFACT_USE_LEGACY_PRINTER=true for EM5820.
    mock_printer = os.getenv("ARTIFACT_MOCK_PRINTER", "false").lower() == "true"
    mock_printer = mock_printer or os.getenv("ARTIFACT_MOCK_HARDWARE", "false").lower() == "true"
    use_legacy_printer = os.getenv("ARTIFACT_USE_LEGACY_PRINTER", "false").lower() == "true"
    printer_manager = PrintManager(
        event_bus=event_bus,
        mock=mock_printer,
        use_legacy_printer=use_legacy_printer
    )
    if use_legacy_printer:
        logger.info("Using legacy EM5820 receipt printer")
    elif printer_manager.is_rp80_printer:
        logger.info("Using RP80 USB receipt printer with cutter")
    else:
        logger.info("Using IP-802 label printer")
    event_bus.subscribe(EventType.PRINT_START, printer_manager.handle_print_start)
    # Start printer in background (don't block main loop!)
    asyncio.create_task(printer_manager.start())
    logger.info("Printer manager starting in background...")

    # Wire up global sound effects for all button events
    def on_button_press(event: Event) -> None:
        runner.play_sound('confirm')

    def on_navigation(event: Event) -> None:
        runner.play_sound('click')

    def on_keypad(event: Event) -> None:
        runner.play_sound('click')

    event_bus.subscribe(EventType.BUTTON_PRESS, on_button_press)
    event_bus.subscribe(EventType.ARCADE_LEFT, on_navigation)
    event_bus.subscribe(EventType.ARCADE_RIGHT, on_navigation)
    event_bus.subscribe(EventType.ARCADE_UP, on_navigation)
    event_bus.subscribe(EventType.ARCADE_DOWN, on_navigation)
    event_bus.subscribe(EventType.KEYPAD_INPUT, on_keypad)

    # Wire up tick handler to update and render
    def on_tick(event: Event) -> None:
        delta = event.data.get("delta", 0.016)
        delta_ms = delta * 1000

        # Update systems
        mode_manager.update(delta_ms)
        animation_engine.update(delta_ms)

        # Render to main display (128x128 HDMI)
        if runner.main_display:
            main_buffer = runner.main_display.get_buffer()
            mode_manager.render_main(main_buffer)
            runner.main_display.set_buffer(main_buffer)

        # Render to ticker display (48x8 WS2812B)
        if runner.ticker_display:
            ticker_buffer = runner.ticker_display.get_buffer()
            mode_manager.render_ticker(ticker_buffer)
            runner.ticker_display.set_buffer(ticker_buffer)

        # Update LCD text
        if runner.lcd_display:
            lcd_text = mode_manager.get_lcd_text()
            runner.lcd_display.set_text(lcd_text)

    event_bus.subscribe(EventType.TICK, on_tick)

    # Run hardware loop
    await runner.run()

    # Cleanup
    await printer_manager.stop()
    camera_service.stop()


def main() -> None:
    """Main entry point."""
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Setup logging
    debug = os.getenv("ARTIFACT_DEBUG", "false").lower() == "true"
    setup_logging(debug)

    logger = logging.getLogger(__name__)
    logger.info("ARTIFACT starting...")

    # Determine environment
    env = os.getenv("ARTIFACT_ENV", "simulator")

    try:
        if env == "simulator":
            logger.info("Running in simulator mode")
            asyncio.run(run_simulator())
        elif env == "hardware":
            logger.info("Running in hardware mode")
            asyncio.run(run_hardware())
        else:
            logger.error(f"Unknown environment: {env}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

    logger.info("ARTIFACT stopped")


if __name__ == "__main__":
    main()
