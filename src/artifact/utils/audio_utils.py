"""Audio utilities for extracting audio from video files.

pygame.mixer.music cannot play audio directly from MP4 video files.
This utility extracts audio to a temporary WAV file using ffmpeg.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import hashlib

logger = logging.getLogger(__name__)

# Cache extracted audio files to avoid re-extraction
_audio_cache: dict[str, Path] = {}
_temp_dir: Optional[Path] = None


def _get_temp_dir() -> Path:
    """Get or create temp directory for extracted audio."""
    global _temp_dir
    if _temp_dir is None or not _temp_dir.exists():
        _temp_dir = Path(tempfile.mkdtemp(prefix="artifact_audio_"))
        logger.info(f"Created audio temp directory: {_temp_dir}")
    return _temp_dir


def _get_cache_key(video_path: Path) -> str:
    """Generate a cache key based on file path and modification time."""
    mtime = video_path.stat().st_mtime if video_path.exists() else 0
    return hashlib.md5(f"{video_path}:{mtime}".encode()).hexdigest()[:12]


def extract_audio_from_video(video_path: Path) -> Optional[Path]:
    """Extract audio from a video file to a temporary WAV file.

    Args:
        video_path: Path to the video file (MP4, etc.)

    Returns:
        Path to the extracted WAV file, or None if extraction failed.
        The WAV file is cached and reused for subsequent calls.
    """
    if not video_path.exists():
        logger.warning(f"Video file not found: {video_path}")
        return None

    # Check for pre-existing audio file with same name
    for ext in ['.wav', '.ogg', '.mp3']:
        audio_path = video_path.with_suffix(ext)
        if audio_path.exists():
            logger.info(f"Found existing audio file: {audio_path}")
            return audio_path

    # Check cache
    cache_key = _get_cache_key(video_path)
    if cache_key in _audio_cache:
        cached_path = _audio_cache[cache_key]
        if cached_path.exists():
            logger.debug(f"Using cached audio: {cached_path}")
            return cached_path

    # Extract audio using ffmpeg
    temp_dir = _get_temp_dir()
    output_path = temp_dir / f"{cache_key}_{video_path.stem}.wav"

    if output_path.exists():
        _audio_cache[cache_key] = output_path
        return output_path

    try:
        # Check if ffmpeg is available
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            logger.warning("ffmpeg not available")
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("ffmpeg not found on system")
        return None

    try:
        logger.info(f"Extracting audio from {video_path.name}...")

        # Extract audio to WAV (most compatible with pygame)
        # -y: overwrite output
        # -i: input file
        # -vn: no video
        # -acodec pcm_s16le: 16-bit PCM audio (standard WAV)
        # -ar 44100: 44.1kHz sample rate
        # -ac 2: stereo
        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                str(output_path)
            ],
            capture_output=True,
            timeout=60  # 1 minute timeout
        )

        if result.returncode == 0 and output_path.exists():
            logger.info(f"Extracted audio to {output_path}")
            _audio_cache[cache_key] = output_path
            return output_path
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            logger.warning(f"ffmpeg failed: {stderr[:200]}")
            return None

    except subprocess.TimeoutExpired:
        logger.warning(f"Audio extraction timed out for {video_path.name}")
        return None
    except Exception as e:
        logger.warning(f"Audio extraction failed: {e}")
        return None


def cleanup_audio_cache() -> None:
    """Clean up temporary audio files."""
    global _audio_cache, _temp_dir

    for path in _audio_cache.values():
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temp audio: {e}")

    _audio_cache.clear()

    if _temp_dir and _temp_dir.exists():
        try:
            import shutil
            shutil.rmtree(_temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean temp dir: {e}")

    _temp_dir = None
    logger.info("Audio cache cleaned up")
