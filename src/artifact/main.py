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
    from artifact.utils.camera_service import camera_service

    # Import ALL game modes
    from artifact.modes.fortune import FortuneMode
    from artifact.modes.roulette import RouletteMode
    from artifact.modes.quiz import QuizMode
    from artifact.modes.ai_prophet import AIProphetMode
    from artifact.modes.squid_game import SquidGameMode
    from artifact.modes.guess_me import GuessMeMode
    from artifact.modes.autopsy import AutopsyMode
    from artifact.modes.roast import RoastMeMode
    from artifact.modes.bar_runner import BarRunnerMode
    from artifact.modes.flow_field import FlowFieldMode
    from artifact.modes.glitch_mirror import GlitchMirrorMode
    from artifact.modes.dither_art import DitherArtMode
    from artifact.modes.ascii_art import AsciiArtMode
    from artifact.modes.brick_breaker import BrickBreakerMode
    from artifact.modes.snake_classic import SnakeClassicMode
    from artifact.modes.snake_tiny import SnakeTinyMode
    from artifact.modes.lunar_lander import LunarLanderMode
    from artifact.modes.pong import PongMode
    from artifact.modes.flappy import FlappyMode
    from artifact.modes.game_2048 import Game2048Mode
    from artifact.modes.tower_stack import TowerStackMode
    from artifact.modes.hand_snake import HandSnakeMode
    from artifact.modes.rocketpy import RocketPyMode
    from artifact.modes.skii import SkiiMode
    from artifact.modes.ninja_fruit import NinjaFruitMode
    from artifact.modes.photobooth import PhotoboothMode
    from artifact.modes.gesture_game import GestureGameMode
    from artifact.modes.rapgod import RapGodMode

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

    # Register ALL game modes - KEY MODES FIRST
    # Priority 1: Main attractions
    mode_manager.register_mode(FortuneMode)       # Fortune teller - classic
    mode_manager.register_mode(PhotoboothMode)    # Photo booth - instant gratification
    mode_manager.register_mode(BrickBreakerMode)  # Brick breaker - addictive arcade
    mode_manager.register_mode(QuizMode)          # Quiz - engaging competition

    # Priority 2: AI-powered experiences
    mode_manager.register_mode(RapGodMode)        # Rap track generator
    mode_manager.register_mode(RoastMeMode)       # AI roasts
    mode_manager.register_mode(GuessMeMode)       # AI guessing game
    mode_manager.register_mode(AutopsyMode)       # X-ray analysis

    # Priority 3: Classic arcade games
    mode_manager.register_mode(SnakeClassicMode)
    mode_manager.register_mode(PongMode)
    mode_manager.register_mode(FlappyMode)
    mode_manager.register_mode(Game2048Mode)
    mode_manager.register_mode(TowerStackMode)
    mode_manager.register_mode(LunarLanderMode)
    mode_manager.register_mode(NinjaFruitMode)
    mode_manager.register_mode(SkiiMode)
    mode_manager.register_mode(RocketPyMode)

    # Priority 4: Camera/gesture modes
    mode_manager.register_mode(GestureGameMode)
    mode_manager.register_mode(SquidGameMode)
    mode_manager.register_mode(HandSnakeMode)

    # Priority 5: Art modes
    mode_manager.register_mode(FlowFieldMode)
    mode_manager.register_mode(GlitchMirrorMode)
    mode_manager.register_mode(DitherArtMode)
    mode_manager.register_mode(AsciiArtMode)

    # Priority 6: Other modes
    mode_manager.register_mode(RouletteMode)
    mode_manager.register_mode(BarRunnerMode)
    mode_manager.register_mode(SnakeTinyMode)

    # AI Prophet mode - needs API key
    if os.environ.get("GEMINI_API_KEY"):
        mode_manager.register_mode(AIProphetMode)
        logger.info("AI Prophet mode enabled (API key found)")
    else:
        logger.warning("AI Prophet mode disabled (no GEMINI_API_KEY)")

    logger.info(f"Registered {len(mode_manager._registered_modes)} modes")

    # Initialize hardware
    if not runner.init():
        logger.error("Hardware initialization failed")
        return

    # Start shared camera service (always-on for instant frames)
    camera_service.start()
    logger.info(f"Camera service: running={camera_service.is_running}")

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

        # Render to hardware display
        if runner.main_display:
            main_buffer = runner.main_display.get_buffer()
            mode_manager.render_main(main_buffer)
            runner.main_display.set_buffer(main_buffer)

    event_bus.subscribe(EventType.TICK, on_tick)

    # Run hardware loop
    await runner.run()

    # Cleanup
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
