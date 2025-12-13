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
from artifact.modes.zodiac import ZodiacMode
from artifact.modes.roulette import RouletteMode
from artifact.modes.quiz import QuizMode
from artifact.modes.ai_prophet import AIProphetMode

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging for simulator."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    # Reduce noise from some modules
    logging.getLogger("artifact.animation").setLevel(logging.INFO)
    logging.getLogger("artifact.graphics").setLevel(logging.INFO)


class ArtifactSimulator:
    """Main simulator application integrating all systems."""

    def __init__(self):
        # Core systems
        self.state_machine = StateMachine()
        self.event_bus = EventBus()
        self.renderer = Renderer()
        self.animation_engine = AnimationEngine()

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
        self.mode_manager.register_mode(ZodiacMode)
        self.mode_manager.register_mode(RouletteMode)
        self.mode_manager.register_mode(QuizMode)

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

        # Run the window (main loop)
        await self.window.run()


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
    logger.info("  SPACE      - Center button (start/confirm)")
    logger.info("  LEFT/RIGHT - Arcade buttons (select/answer)")
    logger.info("  0-9, *, #  - Keypad input")
    logger.info("  F1         - Toggle debug panel")
    logger.info("  ESC        - Exit")
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
