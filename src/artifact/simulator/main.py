"""
Simulator entry point - Fully integrated with mode system.

Runs the ARTIFACT arcade machine in a desktop pygame window.
"""

import asyncio
import logging
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
from artifact.modes.fortune import FortuneMode
from artifact.modes.roulette import RouletteMode
from artifact.modes.quiz import QuizMode
from artifact.modes.ai_prophet import AIProphetMode
from artifact.modes.squid_game import SquidGameMode
from artifact.modes.guess_me import GuessMeMode
from artifact.modes.autopsy import AutopsyMode
from artifact.modes.roast import RoastMeMode
from artifact.modes.tower_stack import TowerStackMode
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
from artifact.modes.stacks import StacksMode
from artifact.modes.towerbrock import TowerbrockMode
from artifact.modes.hand_snake import HandSnakeMode
from artifact.audio.engine import AudioEngine, get_audio_engine
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


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

        # Wire up event handlers
        self._setup_event_handlers()

        logger.info("ArtifactSimulator initialized")

    def _register_modes(self) -> None:
        """Register all available game modes."""
        # Register all game modes
        self.mode_manager.register_mode(FortuneMode)
        self.mode_manager.register_mode(RouletteMode)
        self.mode_manager.register_mode(QuizMode)

        # Squid Game mode - uses webcam for motion detection
        self.mode_manager.register_mode(SquidGameMode)
        
        # New AI Modes
        self.mode_manager.register_mode(GuessMeMode)
        self.mode_manager.register_mode(AutopsyMode)
        self.mode_manager.register_mode(RoastMeMode)

        # Algorithmic Art Modes - visual/interactive modes
        self.mode_manager.register_mode(FlowFieldMode)
        self.mode_manager.register_mode(GlitchMirrorMode)
        self.mode_manager.register_mode(DitherArtMode)
        self.mode_manager.register_mode(AsciiArtMode)
        self.mode_manager.register_mode(TowerStackMode)
        self.mode_manager.register_mode(BarRunnerMode)
        self.mode_manager.register_mode(BrickBreakerMode)
        self.mode_manager.register_mode(SnakeClassicMode)
        self.mode_manager.register_mode(SnakeTinyMode)
        self.mode_manager.register_mode(LunarLanderMode)
        self.mode_manager.register_mode(PongMode)
        self.mode_manager.register_mode(FlappyMode)
        self.mode_manager.register_mode(Game2048Mode)
        self.mode_manager.register_mode(StacksMode)
        self.mode_manager.register_mode(TowerbrockMode)
        self.mode_manager.register_mode(HandSnakeMode)

        # AI Prophet mode - uses webcam and Gemini AI
        import os
        if os.environ.get("GEMINI_API_KEY"):
            self.mode_manager.register_mode(AIProphetMode)
            logger.info("AI Prophet mode enabled (API key found)")
        else:
            logger.warning("AI Prophet mode disabled (no GEMINI_API_KEY)")

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

        # Play printer sound effect
        self.audio.play_reward()

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
    logger.info("  S  - Screenshot")
    logger.info("  Q  - Quit")
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
