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
    from artifact.hardware.runner import HardwareRunner, HardwareConfig

    # Create shared components
    state_machine = StateMachine()
    event_bus = EventBus()

    # Create and run hardware runner
    config = HardwareConfig()
    runner = HardwareRunner(
        config=config,
        state_machine=state_machine,
        event_bus=event_bus
    )

    await runner.run()


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
