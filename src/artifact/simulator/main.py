"""
Simulator entry point.

Direct entry point for running the simulator without
environment detection.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from artifact.simulator.window import SimulatorWindow, WindowConfig
from artifact.core.state import StateMachine
from artifact.core.events import EventBus


def setup_logging() -> None:
    """Configure logging for simulator."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )


async def run() -> None:
    """Run the simulator."""
    # Create shared components
    state_machine = StateMachine()
    event_bus = EventBus()

    # Configure window
    config = WindowConfig(
        width=1280,
        height=720,
        title="ARTIFACT Simulator",
        fps=60
    )

    # Create and run simulator
    window = SimulatorWindow(
        config=config,
        state_machine=state_machine,
        event_bus=event_bus
    )

    await window.run()


def main() -> None:
    """Main entry point for simulator."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting ARTIFACT Simulator...")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    except Exception as e:
        logger.exception(f"Simulator error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
