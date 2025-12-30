"""
Main entry point for ARTIFACT application.

Automatically detects environment (simulator or hardware)
and launches the appropriate version.
"""

import asyncio
import logging
import sys
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
    from artifact.modes.fortune import FortuneMode           # 1. ГАДАЛКА
    from artifact.modes.ai_prophet import AIProphetMode      # 2. ПРОРОК
    from artifact.modes.photobooth import PhotoboothMode     # 3. ФОТОБУДКА
    from artifact.modes.roast import RoastMeMode             # 4. ПРОЖАРКА
    from artifact.modes.guess_me import GuessMeMode          # 5. КТО Я?
    from artifact.modes.squid_game import SquidGameMode      # 6. КАЛЬМАР
    from artifact.modes.quiz import QuizMode                 # 7. КВИЗ
    from artifact.modes.tower_stack import TowerStackMode    # 8. БАШНЯ
    from artifact.modes.brick_breaker import BrickBreakerMode  # 9. КИРПИЧИ
    from artifact.modes.video import VideoMode               # 10. ВИДЕО
    from artifact.modes.gallery import GalleryMode, start_gallery_preloader  # 11. ГАЛЕРЕЯ

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

    # Register curated game modes (same order as simulator)
    # 1. ГАДАЛКА - Fortune teller
    mode_manager.register_mode(FortuneMode)

    # 2. ПРОРОК - AI Prophet (requires API key)
    if os.environ.get("GEMINI_API_KEY"):
        mode_manager.register_mode(AIProphetMode)
        logger.info("AI Prophet mode enabled (API key found)")
    else:
        logger.warning("AI Prophet mode disabled (no GEMINI_API_KEY)")

    # 3. ФОТОБУДКА - Photo booth
    mode_manager.register_mode(PhotoboothMode)

    # 4. ПРОЖАРКА - Roast mode
    mode_manager.register_mode(RoastMeMode)

    # 5. КТО Я? - AI guessing "Who Am I?"
    mode_manager.register_mode(GuessMeMode)

    # 6. КАЛЬМАР - Squid game (red light/green light)
    mode_manager.register_mode(SquidGameMode)

    # 7. КВИЗ - Quiz
    mode_manager.register_mode(QuizMode)

    # 8. БАШНЯ - Tower stack
    mode_manager.register_mode(TowerStackMode)

    # 9. КИРПИЧИ - Brick breaker
    mode_manager.register_mode(BrickBreakerMode)

    # 10. ВИДЕО - Video player
    mode_manager.register_mode(VideoMode)

    # 11. ГАЛЕРЕЯ - Photo gallery slideshow
    mode_manager.register_mode(GalleryMode)

    logger.info(f"Registered {len(mode_manager._registered_modes)} modes")

    # Initialize hardware
    if not runner.init():
        logger.error("Hardware initialization failed")
        return

    # Start shared camera service (always-on for instant frames)
    camera_service.start()
    logger.info(f"Camera service: running={camera_service.is_running}")

    # Start gallery preloader for instant photo loading
    start_gallery_preloader()

    # Initialize printer manager
    mock_printer = os.getenv("ARTIFACT_MOCK_PRINTER", "false").lower() == "true"
    mock_printer = mock_printer or os.getenv("ARTIFACT_MOCK_HARDWARE", "false").lower() == "true"
    printer_manager = PrintManager(event_bus=event_bus, mock=mock_printer)
    event_bus.subscribe(EventType.PRINT_START, printer_manager.handle_print_start)
    await printer_manager.start()

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
