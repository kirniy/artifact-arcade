"""Photobooth Mode - Adapted from raspi-photo-booth with QR sharing.

Photo booth flow:
1. Button press → Countdown (3-2-1)
2. Camera flash → Take photo
3. Show preview → Print + QR code

Original: https://github.com/kriskbx/raspi-photo-booth
QR sharing: Inspired by https://github.com/momentobooth/momentobooth
"""

import time
import tempfile
import subprocess
import random
import io
from typing import Optional
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text
from artifact.utils.camera_service import camera_service

# Try importing QR code library
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


@dataclass
class PhotoboothState:
    """State for photobooth session."""
    countdown: int = 3
    countdown_timer: float = 0.0
    photo_bytes: Optional[bytes] = None
    photo_frame: Optional[NDArray[np.uint8]] = None
    photo_path: Optional[str] = None
    qr_url: Optional[str] = None
    qr_image: Optional[NDArray[np.uint8]] = None
    is_printing: bool = False
    is_uploading: bool = False
    flash_timer: float = 0.0
    show_result: bool = False


class PhotoboothMode(BaseMode):
    """Photobooth mode - take, print, and share photos.

    Adapted from raspi-photo-booth with additions from Momentobooth:
    - Countdown timer with visual + audio feedback
    - Photo capture at high resolution
    - Thermal printing
    - QR code for photo download
    """

    name = "photobooth"
    display_name = "ФОТОБУДКА"
    description = "Сделай фото и получи QR"
    icon = "camera"
    style = "arcade"
    requires_camera = True
    estimated_duration = 20

    # Adapted from raspi-photo-booth
    BEEP_TIME = 0.2
    COUNTDOWN_SECONDS = 3
    FLASH_DURATION = 0.5
    RESULT_DURATION = 15.0

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._state = PhotoboothState()
        self._working = False

    def on_enter(self) -> None:
        """Initialize mode - adapted from raspi-photo-booth setup()."""
        self._state = PhotoboothState()
        self._working = False
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup - adapted from raspi-photo-booth destroy()."""
        self._working = False

    def on_input(self, event: Event) -> bool:
        """Handle button press - adapted from buttonPress()."""
        if event.type not in (EventType.BUTTON_PRESS, EventType.KEYPAD_INPUT):
            return False

        # Prevent re-entry while working (from raspi-photo-booth Working flag)
        if self._working:
            return True

        if self.phase == ModePhase.ACTIVE and not self._state.show_result:
            # Start countdown
            self._working = True
            self._start_countdown()
            return True

        elif self._state.show_result:
            # Reset for another photo
            self._state = PhotoboothState()
            self._working = False
            return True

        return False

    def _start_countdown(self) -> None:
        """Start countdown sequence - adapted from countdown()."""
        self._state.countdown = self.COUNTDOWN_SECONDS
        self._state.countdown_timer = 1.0
        self.change_phase(ModePhase.PROCESSING)

    def on_update(self, delta_ms: float) -> None:
        """Per-frame update - handles countdown and flash."""
        if self.phase == ModePhase.PROCESSING:
            self._update_countdown(delta_ms)
        elif self.phase == ModePhase.RESULT:
            self._update_result(delta_ms)

    def _update_countdown(self, delta_ms: float) -> None:
        """Update countdown timer - adapted from countdown loop."""
        self._state.countdown_timer -= delta_ms / 1000.0

        if self._state.countdown_timer <= 0:
            if self._state.countdown > 1:
                # Next countdown number
                self._state.countdown -= 1
                self._state.countdown_timer = 1.0
            else:
                # Countdown finished - take photo!
                self._do_flash_and_capture()

    def _do_flash_and_capture(self) -> None:
        """Flash and capture - adapted from flashOn + takePhoto."""
        self._state.flash_timer = self.FLASH_DURATION
        self._state.countdown = 0

        # Capture photo using camera_service
        jpeg_bytes = camera_service.capture_jpeg(quality=90)
        if jpeg_bytes:
            self._state.photo_bytes = jpeg_bytes
            self._state.photo_frame = self._decode_photo_frame(jpeg_bytes)

            # Save to temp file for printing
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                f.write(jpeg_bytes)
                self._state.photo_path = f.name

            # Start upload in background (inspired by momentobooth ffsend)
            self._upload_photo_async()

        self.change_phase(ModePhase.RESULT)
        self._state.show_result = True
        self._state.countdown_timer = self.RESULT_DURATION

    def _decode_photo_frame(self, jpeg_bytes: bytes) -> Optional[NDArray[np.uint8]]:
        """Decode captured JPEG into a 128x128 RGB frame for preview."""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(jpeg_bytes))
            img = img.convert("RGB")
            if img.size != (128, 128):
                resample = getattr(Image, "Resampling", Image).BILINEAR
                img = img.resize((128, 128), resample=resample)
            return np.array(img, dtype=np.uint8)
        except Exception:
            return None

    def _upload_photo_async(self) -> None:
        """Upload photo for QR sharing - inspired by momentobooth ffsend."""
        if not self._state.photo_path:
            return

        self._state.is_uploading = True

        # Use file.io for simple upload (alternative to ffsend)
        try:
            import threading
            thread = threading.Thread(target=self._do_upload, daemon=True)
            thread.start()
        except Exception:
            self._state.is_uploading = False

    def _do_upload(self) -> None:
        """Background upload - creates QR code on success."""
        try:
            # Try file.io (simpler than ffsend, works without special client)
            result = subprocess.run(
                ['curl', '-s', '-F', f'file=@{self._state.photo_path}',
                 'https://file.io/?expires=1d'],
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                import json
                response = json.loads(result.stdout.decode())
                if response.get('success'):
                    url = response.get('link')
                    self._state.qr_url = url
                    self._generate_qr_image(url)

        except Exception:
            pass
        finally:
            self._state.is_uploading = False

    def _generate_qr_image(self, url: str) -> None:
        """Generate QR code image for display."""
        if not HAS_QRCODE or not url:
            return

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=2,
                border=1,
            )
            qr.add_data(url)
            qr.make(fit=True)

            # Create image
            from PIL import Image
            img = qr.make_image(fill_color="white", back_color="black")
            img = img.convert('RGB')

            # Resize to fit display (60x60 pixels)
            img = img.resize((60, 60), Image.NEAREST)

            # Convert to numpy array
            self._state.qr_image = np.array(img, dtype=np.uint8)

        except Exception:
            pass

    def _update_result(self, delta_ms: float) -> None:
        """Update result display timer."""
        self._state.countdown_timer -= delta_ms / 1000.0

        if self._state.flash_timer > 0:
            self._state.flash_timer -= delta_ms / 1000.0

        if self._state.countdown_timer <= 0:
            # Auto-return to ready state
            self._complete_session()

    def _complete_session(self) -> None:
        """Complete the session."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "photo_path": self._state.photo_path,
                "qr_url": self._state.qr_url,
            },
            display_text="ФОТО ГОТОВО!",
            ticker_text="ФОТОБУДКА",
            should_print=self._state.photo_path is not None,
            print_data={
                "caricature": self._state.photo_bytes,
                "qr_url": self._state.qr_url,
            }
        )
        self.complete(result)
        self._working = False

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        if self._state.flash_timer > 0:
            # Flash effect (from flashOn)
            fill(buffer, (255, 255, 255))
            return

        # Get camera background
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            np.copyto(buffer, frame)
        else:
            fill(buffer, (20, 15, 30))

        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            # Show countdown number - big and centered
            self._render_countdown(buffer)

        elif self._state.show_result:
            # Show result with QR code
            self._render_result(buffer)

        elif self.phase == ModePhase.ACTIVE:
            # Show "press button" prompt
            self._render_ready(buffer)

    def _render_countdown(self, buffer: NDArray[np.uint8]) -> None:
        """Render countdown number."""
        # Dim camera background
        buffer[:, :, :] = (buffer.astype(np.float32) * 0.3).astype(np.uint8)

        # Big countdown number
        num_str = str(self._state.countdown)
        draw_centered_text(buffer, num_str, 40, (255, 255, 0), scale=6)

    def _render_ready(self, buffer: NDArray[np.uint8]) -> None:
        """Render ready state."""
        # Semi-transparent overlay
        overlay = buffer.copy()
        buffer[:20, :, :] = (overlay[:20, :, :].astype(np.float32) * 0.5).astype(np.uint8)
        buffer[-20:, :, :] = (overlay[-20:, :, :].astype(np.float32) * 0.5).astype(np.uint8)

        # Title and instruction
        draw_centered_text(buffer, "ФОТОБУДКА", 4, (255, 200, 100), scale=1)
        draw_centered_text(buffer, "НАЖМИ", 110, (200, 200, 200), scale=1)
        draw_centered_text(buffer, "КНОПКУ", 120, (200, 200, 200), scale=1)

    def _render_result(self, buffer: NDArray[np.uint8]) -> None:
        """Render result screen with QR code."""
        if self._state.photo_frame is not None:
            np.copyto(buffer, self._state.photo_frame)
        else:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.shape[:2] == (128, 128):
                np.copyto(buffer, frame)
            else:
                fill(buffer, (10, 10, 20))

        overlay = buffer.copy()
        buffer[:18, :, :] = (overlay[:18, :, :].astype(np.float32) * 0.4).astype(np.uint8)
        buffer[-14:, :, :] = (overlay[-14:, :, :].astype(np.float32) * 0.4).astype(np.uint8)

        if self._state.qr_image is not None:
            status_text = "СКАН QR"
        elif self._state.is_uploading:
            status_text = "ЗАГРУЗКА..."
        else:
            status_text = "QR НЕ ГОТОВ"

        draw_centered_text(buffer, status_text, 4, (220, 220, 220), scale=1)

        if self._state.qr_image is not None:
            qr_h, qr_w = self._state.qr_image.shape[:2]
            x_offset = max(4, 128 - qr_w - 4)
            y_offset = max(20, 128 - qr_h - 18)
            draw_rect(buffer, x_offset - 2, y_offset - 2, qr_w + 4, qr_h + 4, (0, 0, 0), filled=True)
            buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = self._state.qr_image

        # Progress bar for auto-exit
        remaining = max(0, self._state.countdown_timer / self.RESULT_DURATION)
        bar_width = int(100 * remaining)
        draw_rect(buffer, 14, 118, bar_width, 4, (80, 80, 80), filled=True)

        draw_centered_text(buffer, "ЕЩЕ РАЗ?", 108, (180, 180, 180), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        fill(buffer, (0, 0, 0))

        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            # Show countdown on ticker
            text = f"   {self._state.countdown}   "
            draw_centered_text(buffer, text, 1, (255, 255, 0), scale=1)
        elif self._state.show_result:
            draw_centered_text(buffer, "ФОТО", 1, (100, 255, 100), scale=1)
        else:
            draw_centered_text(buffer, "ФОТО", 1, (255, 150, 50), scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            return f" ОТСЧЕТ: {self._state.countdown} "[:16].ljust(16)
        elif self._state.show_result:
            return "    ГОТОВО    "[:16]
        else:
            return "   ФОТОБУДКА   "[:16]
