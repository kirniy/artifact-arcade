"""Suno API client for RapTrack mode.

Uses sunoapi.org for AI music generation with Russian vocals.
API docs: https://docs.sunoapi.org/
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class SunoModel(Enum):
    """Available Suno models.

    API uses uppercase model names without 'chirp-' prefix.
    See: https://docs.sunoapi.org/suno-api/generate-music
    """

    V4 = "V4"  # 4 min max, best audio quality
    V4_5 = "V4_5"  # 8 min max, smarter prompts
    V4_5_ALL = "V4_5ALL"  # 8 min max, better song structure
    V4_5_PLUS = "V4_5PLUS"  # 8 min max, richer sound
    V5 = "V5"  # Superior musical expression, faster


class TrackStatus(Enum):
    """Track generation status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SunoTrack:
    """Generated track metadata."""

    task_id: str
    status: TrackStatus
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class SunoClient:
    """Client for sunoapi.org music generation API."""

    BASE_URL = "https://api.sunoapi.org"

    # Fibonacci backoff intervals for polling (seconds)
    POLL_INTERVALS = [2, 3, 5, 8, 13, 21, 34]

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SUNO_API_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None

        if not self._api_key:
            logger.warning("SUNO_API_KEY not set, music generation will be disabled")

    @property
    def is_available(self) -> bool:
        """Check if music generation is available."""
        return bool(self._api_key)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def generate_track(
        self,
        lyrics: str,
        title: str,
        style: str = "russian trap, club banger, aggressive 808s",
        model: SunoModel = SunoModel.V4_5,
        is_instrumental: bool = False,
    ) -> Optional[str]:
        """Generate a music track with vocals.

        Args:
            lyrics: Song lyrics (hook + verse)
            title: Track title
            style: Music style description
            model: Suno model to use
            is_instrumental: If True, generate without vocals

        Returns:
            Task ID for polling, or None on error
        """
        if not self.is_available:
            logger.error("Suno API not available (no API key)")
            return None

        try:
            session = await self._ensure_session()

            # Build request payload
            # See: https://docs.sunoapi.org/suno-api/music-generation/
            payload = {
                "prompt": lyrics,
                "style": style,
                "title": title,
                "customMode": True,  # Use custom lyrics mode
                "instrumental": is_instrumental,
                "model": model.value,
                # callBackUrl is required but we use polling instead
                "callBackUrl": "https://vnvnc.ai/webhook/suno",
            }

            logger.info(f"Generating track: {title} (model={model.value})")

            async with session.post(
                f"{self.BASE_URL}/api/v1/generate",
                json=payload,
            ) as response:
                if response.status == 401:
                    logger.error("Suno API authentication failed")
                    return None

                if response.status == 402:
                    logger.error("Suno API: insufficient credits")
                    return None

                if not response.ok:
                    error_text = await response.text()
                    logger.error(f"Suno API error {response.status}: {error_text}")
                    return None

                data = await response.json()

                # Extract task ID from response
                task_id = data.get("taskId") or data.get("task_id")
                if not task_id:
                    # Some responses return the task ID in a different field
                    if isinstance(data.get("data"), dict):
                        task_id = data["data"].get("taskId")

                if task_id:
                    logger.info(f"Track generation started: task_id={task_id}")
                    return task_id
                else:
                    logger.error(f"No task_id in response: {data}")
                    return None

        except asyncio.TimeoutError:
            logger.error("Suno API request timed out")
            return None
        except Exception as e:
            logger.error(f"Suno API error: {e}")
            return None

    async def get_status(self, task_id: str) -> SunoTrack:
        """Get the status of a generation task.

        Args:
            task_id: Task ID from generate_track()

        Returns:
            SunoTrack with current status and URLs if complete
        """
        if not self.is_available:
            return SunoTrack(
                task_id=task_id,
                status=TrackStatus.FAILED,
                error="API not available",
            )

        try:
            session = await self._ensure_session()

            async with session.get(
                f"{self.BASE_URL}/api/v1/generate/record-info",
                params={"id": task_id},
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    logger.warning(f"Status check failed: {error_text}")
                    return SunoTrack(
                        task_id=task_id,
                        status=TrackStatus.FAILED,
                        error=f"HTTP {response.status}",
                    )

                data = await response.json()

                # Parse response
                # The API may return data in different structures
                record = data.get("data") or data

                # Handle list response (multiple tracks per task)
                if isinstance(record, list) and len(record) > 0:
                    record = record[0]

                status_str = str(record.get("status", "")).lower()

                # Map status strings to enum
                if status_str in ("complete", "completed", "success"):
                    status = TrackStatus.COMPLETED
                elif status_str in ("failed", "error"):
                    status = TrackStatus.FAILED
                elif status_str in ("processing", "running", "generating"):
                    status = TrackStatus.PROCESSING
                else:
                    status = TrackStatus.PENDING

                # Extract URLs
                audio_url = record.get("audioUrl") or record.get("audio_url")
                video_url = record.get("videoUrl") or record.get("video_url")
                image_url = record.get("imageUrl") or record.get("image_url")

                # Duration might be in seconds or formatted string
                duration = record.get("duration")
                if isinstance(duration, str):
                    # Parse "MM:SS" format
                    try:
                        parts = duration.split(":")
                        duration = int(parts[0]) * 60 + int(parts[1])
                    except Exception:
                        duration = None

                return SunoTrack(
                    task_id=task_id,
                    status=status,
                    audio_url=audio_url,
                    video_url=video_url,
                    image_url=image_url,
                    title=record.get("title"),
                    duration=duration,
                    error=record.get("errorMessage"),
                    raw_response=data,
                )

        except Exception as e:
            logger.error(f"Status check error: {e}")
            return SunoTrack(
                task_id=task_id,
                status=TrackStatus.FAILED,
                error=str(e),
            )

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: float = 90.0,
        on_progress: Optional[callable] = None,
    ) -> SunoTrack:
        """Wait for track generation to complete.

        Args:
            task_id: Task ID from generate_track()
            timeout: Maximum wait time in seconds
            on_progress: Optional callback(progress_pct: float) for updates

        Returns:
            SunoTrack with final status and URLs
        """
        start_time = asyncio.get_event_loop().time()
        poll_index = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                logger.warning(f"Track generation timed out after {timeout}s")
                return SunoTrack(
                    task_id=task_id,
                    status=TrackStatus.PROCESSING,  # Still processing, not failed
                    error="Timeout - track may still be generating",
                )

            # Get current status with timeout protection
            try:
                track = await asyncio.wait_for(
                    self.get_status(task_id),
                    timeout=15.0  # 15s timeout per status check
                )
            except asyncio.TimeoutError:
                logger.warning(f"Status check timed out, retrying... (elapsed: {elapsed:.1f}s)")
                poll_index += 1
                continue

            logger.debug(f"Poll {poll_index}: status={track.status.value}, elapsed={elapsed:.1f}s")

            if track.status == TrackStatus.COMPLETED:
                logger.info(f"Track completed: {track.audio_url}")
                return track

            if track.status == TrackStatus.FAILED:
                logger.error(f"Track generation failed: {track.error}")
                return track

            # Report progress (estimate based on typical 30-40s generation)
            if on_progress:
                progress = min(0.95, elapsed / 40.0)  # Cap at 95%
                on_progress(progress)

            # Wait before next poll (Fibonacci backoff)
            interval = self.POLL_INTERVALS[min(poll_index, len(self.POLL_INTERVALS) - 1)]
            await asyncio.sleep(interval)
            poll_index += 1

    async def download_audio(self, audio_url: str) -> Optional[bytes]:
        """Download audio file from URL.

        Args:
            audio_url: URL to download

        Returns:
            Audio bytes or None on error
        """
        try:
            session = await self._ensure_session()

            async with session.get(audio_url) as response:
                if not response.ok:
                    logger.error(f"Audio download failed: {response.status}")
                    return None

                audio_bytes = await response.read()
                logger.info(f"Downloaded {len(audio_bytes)} bytes of audio")
                return audio_bytes

        except Exception as e:
            logger.error(f"Audio download error: {e}")
            return None

    async def get_credits(self) -> Optional[int]:
        """Get remaining API credits.

        Returns:
            Number of credits remaining, or None on error
        """
        if not self.is_available:
            return None

        try:
            session = await self._ensure_session()

            async with session.get(
                f"{self.BASE_URL}/api/v1/generate/credit"
            ) as response:
                if not response.ok:
                    return None

                data = await response.json()
                credits = data.get("credits") or data.get("data", {}).get("credits")
                return credits

        except Exception as e:
            logger.error(f"Credits check error: {e}")
            return None


# Module-level singleton
_client: Optional[SunoClient] = None


def get_suno_client() -> SunoClient:
    """Get the singleton Suno client instance."""
    global _client
    if _client is None:
        _client = SunoClient()
    return _client


# Quick test
if __name__ == "__main__":
    import sys

    async def test():
        client = SunoClient()

        if not client.is_available:
            print("SUNO_API_KEY not set")
            return

        # Check credits
        credits = await client.get_credits()
        print(f"Credits remaining: {credits}")

        # Test generation
        task_id = await client.generate_track(
            lyrics="Вайб на бите, краш в душе\nФлекс это мы, ты слышишь?\nARTIFACT качает, это наш вайб\nНочь только началась, давай!",
            title="Test Track",
            style="russian trap, club banger, 140 bpm",
        )

        if task_id:
            print(f"Task started: {task_id}")

            def on_progress(pct):
                print(f"Progress: {pct * 100:.0f}%")

            track = await client.wait_for_completion(
                task_id,
                timeout=120.0,
                on_progress=on_progress,
            )

            print(f"Status: {track.status}")
            print(f"Audio URL: {track.audio_url}")

        await client.close()

    asyncio.run(test())
