"""Camera utilities - environment-aware camera access.

Automatically uses hardware camera on Pi (ARTIFACT_ENV=hardware)
and simulator camera on Mac/desktop.
"""

import os
from typing import Tuple

# Environment detection
IS_HARDWARE = os.getenv("ARTIFACT_ENV") == "hardware"

# Import the appropriate camera implementation
if IS_HARDWARE:
    from artifact.hardware.camera import PiCamera as Camera, create_camera, is_pi_camera_available
else:
    from artifact.simulator.mock_hardware.camera import SimulatorCamera as Camera, create_camera

    def is_pi_camera_available() -> bool:
        """Pi camera not available on non-hardware platforms."""
        return False

# Import dithering utilities (work on any platform)
from artifact.simulator.mock_hardware.camera import (
    floyd_steinberg_dither,
    create_viewfinder_overlay,
)

__all__ = [
    "Camera",
    "create_camera",
    "is_pi_camera_available",
    "floyd_steinberg_dither",
    "create_viewfinder_overlay",
    "IS_HARDWARE",
]
