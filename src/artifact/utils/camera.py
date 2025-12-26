"""Camera utilities - environment-aware camera access.

Automatically uses hardware camera on Pi (ARTIFACT_ENV=hardware)
and simulator camera on Mac/desktop.

RECOMMENDED: Use the shared camera_service for instant frame access:
    from artifact.utils.camera_service import camera_service
    frame = camera_service.get_frame()  # Instant!
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

# Import shared camera service (recommended way to access camera)
from artifact.utils.camera_service import camera_service, get_camera_service, CameraService

__all__ = [
    "Camera",
    "create_camera",
    "is_pi_camera_available",
    "floyd_steinberg_dither",
    "create_viewfinder_overlay",
    "IS_HARDWARE",
    # Shared camera service (recommended)
    "camera_service",
    "get_camera_service",
    "CameraService",
]
