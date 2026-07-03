"""
HDMI Display driver for NovaStar T50 + DH418 LED panel system.

The T50 receives HDMI input and forwards it to the DH418 receiver card,
which drives the HUB75E LED panels. From the Pi's perspective, we just
output standard video via HDMI - the T50/DH418 handle all panel driving.

IMPORTANT: On Raspberry Pi with kmsdrm, we output 720x480 via HDMI.
The T50 is configured to crop the top-left 128x128 pixels for the LED panels.
This approach works because kmsdrm needs a standard resolution, not 128x128.
"""

import logging
import os
import time
import numpy as np
from numpy.typing import NDArray
from typing import Any

from ..base import Display

logger = logging.getLogger(__name__)

# Pygame import is deferred to avoid issues on non-Pi systems
_pygame = None


def _get_pygame():
    """Lazy import pygame - let it auto-detect video driver."""
    global _pygame
    if _pygame is None:
        # NOTE: Do NOT set SDL_VIDEODRIVER=kmsdrm explicitly on Debian Trixie!
        # Let pygame auto-detect the driver - explicit setting breaks initialization.
        import pygame
        _pygame = pygame
    return _pygame


# HDMI output resolution (standard resolution for T50 compatibility)
HDMI_OUTPUT_WIDTH = 720
HDMI_OUTPUT_HEIGHT = 480


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _find_mode(connector: Any, width: int, height: int) -> Any:
    for mode in connector.get_modes():
        if int(getattr(mode, "hdisplay", 0)) == width and int(getattr(mode, "vdisplay", 0)) == height:
            return mode
    return connector.get_current_crtc().mode


class _KMSOutput:
    def __init__(self, card: Any, connector_name: str, width: int, height: int) -> None:
        import pykms

        connector = next((c for c in card.connectors if c.fullname == connector_name), None)
        if connector is None:
            raise RuntimeError(f"DRM connector not found: {connector_name}")
        if not connector.connected():
            raise RuntimeError(f"DRM connector is not connected: {connector_name}")

        crtc = connector.get_current_crtc()
        if crtc is None:
            raise RuntimeError(f"DRM connector has no active CRTC: {connector_name}")

        mode = _find_mode(connector, width, height)
        self.width = int(getattr(mode, "hdisplay", width))
        self.height = int(getattr(mode, "vdisplay", height))
        self.connector_name = connector_name
        self.crtc = crtc
        self.plane = crtc.primary_plane
        self.fb = pykms.DumbFramebuffer(card, self.width, self.height, pykms.PixelFormat.XRGB8888)
        self.view = self.fb.map(0).cast("B")
        self.stride = self.fb.stride(0)

        current_mode = crtc.mode
        current_width = int(getattr(current_mode, "hdisplay", 0))
        current_height = int(getattr(current_mode, "vdisplay", 0))
        if (current_width, current_height) != (self.width, self.height):
            result = crtc.set_mode(connector, self.fb, mode)
            if result < 0:
                raise RuntimeError(f"Failed to set DRM mode {self.width}x{self.height} on {connector_name}: {result}")

    def show_rgb(self, frame: NDArray[np.uint8]) -> None:
        h, w = frame.shape[:2]
        if (w, h) != (self.width, self.height):
            raise ValueError(f"Frame size {w}x{h} does not match {self.connector_name} {self.width}x{self.height}")

        xrgb = np.empty((h, w, 4), dtype=np.uint8)
        xrgb[:, :, 0] = frame[:, :, 2]
        xrgb[:, :, 1] = frame[:, :, 1]
        xrgb[:, :, 2] = frame[:, :, 0]
        xrgb[:, :, 3] = 0

        row_bytes = w * 4
        raw = xrgb.reshape(-1)
        if self.stride == row_bytes:
            self.view[: row_bytes * h] = raw.tobytes()
        else:
            for y in range(h):
                dst_start = y * self.stride
                src_start = y * row_bytes
                self.view[dst_start : dst_start + row_bytes] = raw[src_start : src_start + row_bytes].tobytes()

        self.fb.flush()
        result = self.crtc.set_plane(self.plane, self.fb, 0, 0, w, h, 0, 0, float(w), float(h))
        if result < 0:
            raise RuntimeError(f"Failed to set DRM plane {self.plane.id} on {self.connector_name}: {result}")


class HDMIDisplayKMSDual(Display):
    """Single-process KMS backend for photobooth HDMI plus optional TV wall HDMI."""

    def __init__(self, width: int = 128, height: int = 128, rotate_180: bool = True):
        self._width = width
        self._height = height
        self._rotate_180 = rotate_180
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._initialized = False
        self._card = None
        self._main_output = None
        self._wall_output = None
        self._wall_renderer = None
        self._wall_enabled = _env_enabled("VNVNC_INPROCESS_TV_WALL_ENABLED", False)
        self._last_wall_update = 0.0
        self._wall_frame: NDArray[np.uint8] | None = None
        self._show_count = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def init(self) -> bool:
        if self._initialized:
            return True

        try:
            import pykms

            card_path = os.environ.get("VNVNC_DUAL_KMS_DRM_CARD", "/dev/dri/card1")
            self._card = pykms.Card(card_path)
            self._main_output = _KMSOutput(
                self._card,
                os.environ.get("VNVNC_MAIN_DRM_CONNECTOR", "HDMI-A-1"),
                HDMI_OUTPUT_WIDTH,
                HDMI_OUTPUT_HEIGHT,
            )
            if self._wall_enabled:
                self._wall_output = _KMSOutput(
                    self._card,
                    os.environ.get("VNVNC_VIDEO_WALL_DRM_CONNECTOR", "HDMI-A-2"),
                    int(os.environ.get("VNVNC_VIDEO_WALL_OUTPUT_WIDTH", "1280")),
                    int(os.environ.get("VNVNC_VIDEO_WALL_OUTPUT_HEIGHT", "720")),
                )
                from ...video_wall.renderer import VideoWallConfig, VideoWallRenderer

                config = VideoWallConfig()
                config.output_width = self._wall_output.width
                config.output_height = self._wall_output.height
                self._wall_renderer = VideoWallRenderer(config)
                self._wall_renderer._open_capture(required=False)

            self._initialized = True
            logger.info(
                "KMS dual HDMI initialized: main=%sx%s wall=%s",
                self._main_output.width,
                self._main_output.height,
                f"{self._wall_output.width}x{self._wall_output.height}" if self._wall_output else "off",
            )
            return True
        except Exception as e:
            logger.error("Failed to initialize KMS dual HDMI display: %s", e)
            return False

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)
        else:
            h = min(buffer.shape[0], self._height)
            w = min(buffer.shape[1], self._width)
            self._buffer[:h, :w] = buffer[:h, :w]

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._buffer[:, :] = [r, g, b]

    def show(self) -> None:
        if not self._initialized or self._main_output is None:
            return

        main_frame = np.zeros((self._main_output.height, self._main_output.width, 3), dtype=np.uint8)
        led = np.rot90(self._buffer, 2) if self._rotate_180 else self._buffer
        main_frame[: self._height, : self._width] = led
        self._main_output.show_rgb(main_frame)

        if self._wall_output is not None and self._wall_renderer is not None:
            self._show_wall_frame()

        self._show_count += 1
        if self._show_count % 60 == 0:
            logger.info("KMS dual display frame %s", self._show_count)

    def _show_wall_frame(self) -> None:
        assert self._wall_output is not None
        assert self._wall_renderer is not None

        now = time.time()
        interval = 1.0 / max(1, getattr(self._wall_renderer.config, "capture_fps", 25))
        if self._wall_frame is None or now - self._last_wall_update >= interval:
            raw = self._wall_renderer._next_source_frame()
            if raw is None:
                raw = self._wall_renderer._placeholder_frame(now)
            self._wall_renderer._publish_shared_frame(raw)
            self._wall_frame = self._wall_renderer._render_frame(raw, now)
            self._wall_renderer._touch_heartbeat()
            self._last_wall_update = now

        self._wall_output.show_rgb(self._wall_frame)

    def get_buffer(self) -> NDArray[np.uint8]:
        return self._buffer.copy()

    def cleanup(self) -> None:
        if self._wall_renderer is not None:
            self._wall_renderer._cleanup()
            self._wall_renderer = None
        self._main_output = None
        self._wall_output = None
        self._card = None
        self._initialized = False
        logger.info("KMS dual HDMI display cleaned up")


class HDMIDisplay(Display):
    """
    HDMI display driver for T50 + DH418 LED matrix system.

    Outputs 720x480 via HDMI with the 128x128 content in the top-left corner.
    The NovaStar T50 is configured to crop the top-left 128x128 pixels,
    which then get sent to the DH418 receiver card driving the LED panels.

    This approach is needed because kmsdrm requires standard video resolutions,
    and 128x128 is not a valid HDMI mode.

    Usage:
        display = HDMIDisplay()
        display.init()

        # Draw something
        display.clear(255, 0, 0)  # Red
        display.show()

        # Or use buffer
        buffer = np.zeros((128, 128, 3), dtype=np.uint8)
        buffer[:, :] = [0, 255, 0]  # Green
        display.set_buffer(buffer)
        display.show()

        # Flip display 180° if mounted upside down
        display = HDMIDisplay(rotate_180=True)
    """

    def __init__(self, width: int = 128, height: int = 128, rotate_180: bool = True):
        self._width = width
        self._height = height
        self._rotate_180 = rotate_180
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._screen = None
        self._led_surface = None  # The 128x128 surface for LED content
        self._initialized = False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def init(self) -> bool:
        """
        Initialize the HDMI display.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        try:
            pygame = _get_pygame()

            # Initialize pygame display
            pygame.init()
            pygame.display.init()

            # Set up fullscreen display FIRST - required for kmsdrm driver
            self._screen = pygame.display.set_mode(
                (HDMI_OUTPUT_WIDTH, HDMI_OUTPUT_HEIGHT),
                pygame.FULLSCREEN
            )

            # Hide mouse cursor AFTER set_mode (kmsdrm requirement)
            pygame.mouse.set_visible(False)

            # Create surface for the 128x128 LED content
            self._led_surface = pygame.Surface((self._width, self._height))

            pygame.display.set_caption("ARTIFACT")

            logger.info(f"Video driver: {pygame.display.get_driver()}")

            # Clear to black initially
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

            self._initialized = True
            logger.info(
                f"HDMI display initialized: {HDMI_OUTPUT_WIDTH}x{HDMI_OUTPUT_HEIGHT} "
                f"(LED area: {self._width}x{self._height} in top-left)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize HDMI display: {e}")
            return False

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color."""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        """Set entire display buffer."""
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)
        else:
            # Handle size mismatch
            h = min(buffer.shape[0], self._height)
            w = min(buffer.shape[1], self._width)
            self._buffer[:h, :w] = buffer[:h, :w]

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        """Clear display to specified color."""
        self._buffer[:, :] = [r, g, b]

    _show_count = 0  # Class variable for counting calls

    def show(self) -> None:
        """Update physical display with buffer contents."""
        if not self._initialized or self._screen is None:
            return

        pygame = _get_pygame()
        try:
            pygame.mouse.set_visible(False)
        except Exception:
            pass

        # Convert numpy buffer to pygame surface
        # pygame expects (width, height) but numpy is (height, width)
        surface = pygame.surfarray.make_surface(
            self._buffer.swapaxes(0, 1)
        )

        # Rotate 180° if display is mounted upside down
        if self._rotate_180:
            surface = pygame.transform.rotate(surface, 180)

        # Clear screen to black first
        self._screen.fill((0, 0, 0))

        # Blit LED content to top-left corner (T50 crops this region)
        self._screen.blit(surface, (0, 0))

        # DEBUG: Log every 60 frames (1 second at 60fps)
        HDMIDisplay._show_count += 1
        if HDMIDisplay._show_count % 60 == 0:
            logger.info(f"pygame.display.flip() called (frame {HDMIDisplay._show_count})")

        pygame.display.flip()

    def get_buffer(self) -> NDArray[np.uint8]:
        """Get copy of current display buffer."""
        return self._buffer.copy()

    def cleanup(self) -> None:
        """Clean up pygame resources."""
        if self._initialized:
            pygame = _get_pygame()
            pygame.display.quit()
            pygame.quit()
            self._initialized = False
            logger.info("HDMI display cleaned up")

    def __del__(self):
        self.cleanup()


class HDMIDisplayScaled(HDMIDisplay):
    """
    HDMI display with upscaling for better visibility on standard monitors.

    Use this if T50 doesn't receive 128x128 properly and needs a larger
    resolution. The content is scaled up with nearest-neighbor filtering
    to maintain the pixel-art look.
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 128,
        scale: int = 4,
        rotate_180: bool = True
    ):
        super().__init__(width, height, rotate_180=rotate_180)
        self._scale = scale
        self._output_width = width * scale
        self._output_height = height * scale

    def init(self) -> bool:
        """Initialize with scaled output resolution."""
        if self._initialized:
            return True

        try:
            pygame = _get_pygame()

            pygame.init()
            pygame.display.init()
            pygame.mouse.set_visible(False)

            # Use scaled resolution
            self._screen = pygame.display.set_mode(
                (self._output_width, self._output_height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )

            pygame.display.set_caption("ARTIFACT")
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

            self._initialized = True
            logger.info(
                f"HDMI display initialized: {self._width}x{self._height} "
                f"scaled to {self._output_width}x{self._output_height}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize HDMI display: {e}")
            return False

    def show(self) -> None:
        """Update display with scaled buffer."""
        if not self._initialized or self._screen is None:
            return

        pygame = _get_pygame()

        # Create surface from buffer
        surface = pygame.surfarray.make_surface(
            self._buffer.swapaxes(0, 1)
        )

        # Rotate 180° if display is mounted upside down
        if self._rotate_180:
            surface = pygame.transform.rotate(surface, 180)

        # Scale up with nearest-neighbor (preserves pixel-art look)
        scaled = pygame.transform.scale(
            surface,
            (self._output_width, self._output_height)
        )

        self._screen.blit(scaled, (0, 0))
        pygame.display.flip()
