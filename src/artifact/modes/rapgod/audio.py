"""Audio utilities for RapTrack mode.

Handles audio playback and Selectel S3 upload for QR sharing.
"""

import os
import asyncio
import logging
import tempfile
import subprocess
from typing import Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import aiohttp

from artifact.utils.s3_upload import upload_bytes_to_s3, generate_qr_image as generate_qr_numpy

logger = logging.getLogger(__name__)

# Thread pool for running sync S3 uploads asynchronously
_executor = ThreadPoolExecutor(max_workers=2)


class AudioPlayer:
    """Audio playback for generated tracks."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._temp_file: Optional[Path] = None

    async def play_preview(
        self,
        audio_bytes: bytes,
        duration_sec: float = 12.0,
        device: str = "hw:2,0",
    ) -> bool:
        """Play audio preview for a limited duration.

        Args:
            audio_bytes: MP3 audio data
            duration_sec: How long to play (seconds)
            device: ALSA device (hw:2,0 = 3.5mm jack on Pi)

        Returns:
            True if playback started successfully
        """
        try:
            # Stop any existing playback
            await self.stop()

            # Save to temp file
            self._temp_file = Path(tempfile.mktemp(suffix=".mp3"))
            self._temp_file.write_bytes(audio_bytes)

            logger.info(f"Playing audio preview ({duration_sec}s) on {device}")

            # Try pygame first (if available)
            try:
                import pygame

                # Initialize mixer with specific device
                os.environ["SDL_AUDIODRIVER"] = "alsa"
                os.environ["AUDIODEV"] = device

                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

                pygame.mixer.music.load(str(self._temp_file))
                pygame.mixer.music.play()

                # Schedule stop after duration
                asyncio.get_event_loop().call_later(
                    duration_sec,
                    lambda: pygame.mixer.music.stop() if pygame.mixer.get_init() else None
                )

                logger.info("Playback started via pygame")
                return True

            except ImportError:
                logger.info("pygame not available, falling back to aplay")

            # Fallback to aplay (subprocess)
            self._process = subprocess.Popen(
                [
                    "timeout", str(duration_sec),
                    "aplay", "-D", device, "-q", str(self._temp_file),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            logger.info("Playback started via aplay")
            return True

        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
            return False

    async def stop(self) -> None:
        """Stop any active playback."""
        try:
            # Stop pygame mixer
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except ImportError:
                pass

            # Kill subprocess
            if self._process and self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=1)
                self._process = None

            # Cleanup temp file
            if self._temp_file and self._temp_file.exists():
                self._temp_file.unlink()
                self._temp_file = None

        except Exception as e:
            logger.warning(f"Error stopping playback: {e}")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            if self._temp_file and self._temp_file.exists():
                self._temp_file.unlink()
        except Exception:
            pass


async def upload_to_selectel(
    audio_bytes: bytes,
    filename: str = "track.mp3",
) -> Optional[str]:
    """Upload audio to Selectel S3 for QR sharing.

    Args:
        audio_bytes: MP3 audio data
        filename: Filename for the upload (unused, auto-generated)

    Returns:
        Shareable URL or None on error
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            lambda: upload_bytes_to_s3(audio_bytes, "track", "mp3", "audio/mpeg")
        )

        if result.success:
            logger.info(f"Uploaded to Selectel S3: {result.url}")
            return result.url
        else:
            logger.error(f"Selectel S3 upload failed: {result.error}")
            return None

    except Exception as e:
        logger.error(f"Selectel S3 upload error: {e}")
        return None


# Keep old function name as alias for backwards compatibility
upload_to_fileio = upload_to_selectel


async def generate_qr_image(url: str, size: int = 60) -> Optional[bytes]:
    """Generate a QR code image for the URL.

    Args:
        url: URL to encode
        size: Output image size in pixels

    Returns:
        PNG image bytes or None on error
    """
    try:
        import qrcode
        from PIL import Image
        import io

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=2,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # White on black for LED display visibility
        img = qr.make_image(fill_color="white", back_color="black")
        img = img.resize((size, size), Image.NEAREST)

        # Convert to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    except ImportError:
        logger.warning("qrcode library not available")
        return None
    except Exception as e:
        logger.error(f"QR generation failed: {e}")
        return None


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "2:45"
    """
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


# Quick test
if __name__ == "__main__":
    async def test():
        # Test file.io upload
        test_data = b"test audio data" * 1000
        url = await upload_to_fileio(test_data, "test.mp3")
        print(f"Uploaded to: {url}")

        if url:
            # Test QR generation
            qr_bytes = await generate_qr_image(url)
            if qr_bytes:
                print(f"QR code: {len(qr_bytes)} bytes")

    asyncio.run(test())
