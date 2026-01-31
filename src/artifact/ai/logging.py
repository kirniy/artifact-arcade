"""AI Generation Logging System for VNVNC.

Saves all AI-generated content (text predictions, images, caricatures)
to a structured log directory with metadata.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import base64

logger = logging.getLogger(__name__)

# Default log directory - relative to project root
# Gets the project root by going up from src/artifact/ai/logging.py
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent  # src/artifact/ai -> src/artifact -> src -> project root
DEFAULT_LOG_DIR = str(_PROJECT_ROOT / "vnvnc_ai_logs")


class AILogger:
    """Singleton logger for all AI generations.

    Saves to structured directories:
    <project_root>/vnvnc_ai_logs/
    ├── YYYY-MM-DD/
    │   ├── text/
    │   │   ├── fortune_HHMMSS_uuid.json
    │   │   ├── prediction_HHMMSS_uuid.json
    │   │   └── ...
    │   ├── images/
    │   │   ├── caricature_HHMMSS_uuid.png
    │   │   └── ...
    │   └── metadata/
    │       └── session_HHMMSS.json
    """

    _instance: Optional["AILogger"] = None
    _initialized: bool = False

    def __new__(cls, log_dir: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: Optional[str] = None):
        if self._initialized:
            return

        self.log_dir = Path(log_dir or DEFAULT_LOG_DIR)
        self._ensure_directories()
        self._session_id = datetime.now().strftime("%H%M%S")
        self._initialized = True
        logger.info(f"AILogger initialized at {self.log_dir}")

    def _ensure_directories(self) -> None:
        """Create log directories if they don't exist."""
        today = datetime.now().strftime("%Y-%m-%d")
        day_dir = self.log_dir / today

        for subdir in ["text", "images", "metadata"]:
            (day_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _get_day_dir(self) -> Path:
        """Get today's log directory."""
        today = datetime.now().strftime("%Y-%m-%d")
        day_dir = self.log_dir / today
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _generate_id(self) -> str:
        """Generate unique ID for log entries."""
        import uuid
        return f"{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def log_text_generation(
        self,
        category: str,
        prompt: str,
        response: str,
        model: str,
        mode_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a text generation result.

        Args:
            category: Type of generation (fortune, prediction, roast, etc.)
            prompt: The prompt sent to AI
            response: AI's response text
            model: Model used for generation
            mode_name: Mode that triggered this generation
            metadata: Additional context data

        Returns:
            Log entry ID
        """
        try:
            entry_id = self._generate_id()
            day_dir = self._get_day_dir()

            log_entry = {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "mode": mode_name,
                "model": model,
                "prompt": prompt,
                "response": response,
                "metadata": metadata or {},
            }

            # Save to JSON file
            filename = f"{category}_{entry_id}.json"
            filepath = day_dir / "text" / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)

            logger.debug(f"Logged text generation: {filepath}")
            return entry_id

        except Exception as e:
            logger.error(f"Failed to log text generation: {e}")
            return ""

    def log_image_generation(
        self,
        category: str,
        image_data: bytes,
        prompt: Optional[str] = None,
        model: str = "unknown",
        mode_name: Optional[str] = None,
        style: Optional[str] = None,
        reference_photo: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an image generation result.

        Args:
            category: Type of image (caricature, portrait, doodle, etc.)
            image_data: Generated image bytes (PNG/JPEG)
            prompt: The prompt used for generation
            model: Model used for generation
            mode_name: Mode that triggered this generation
            style: Style/type of the image
            reference_photo: Original photo if applicable
            metadata: Additional context data

        Returns:
            Log entry ID
        """
        try:
            entry_id = self._generate_id()
            day_dir = self._get_day_dir()

            # Save the generated image
            img_filename = f"{category}_{entry_id}.png"
            img_filepath = day_dir / "images" / img_filename

            with open(img_filepath, "wb") as f:
                f.write(image_data)

            # Save reference photo if provided (deduplicated by hash)
            ref_filename = None
            if reference_photo:
                import hashlib
                photo_hash = hashlib.md5(reference_photo).hexdigest()[:12]
                ref_filename = f"ref_{photo_hash}.jpg"
                ref_filepath = day_dir / "images" / ref_filename
                
                # Only save if it doesn't exist yet
                if not ref_filepath.exists():
                    with open(ref_filepath, "wb") as f:
                        f.write(reference_photo)

            # Save metadata
            meta_entry = {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "mode": mode_name,
                "model": model,
                "style": style,
                "prompt": prompt,
                "image_file": img_filename,
                "reference_file": ref_filename,
                "metadata": metadata or {},
            }

            meta_filename = f"{category}_{entry_id}_meta.json"
            meta_filepath = day_dir / "metadata" / meta_filename

            with open(meta_filepath, "w", encoding="utf-8") as f:
                json.dump(meta_entry, f, ensure_ascii=False, indent=2)

            logger.debug(f"Logged image generation: {img_filepath}")
            return entry_id

        except Exception as e:
            logger.error(f"Failed to log image generation: {e}")
            return ""

    def log_session_summary(
        self,
        mode_name: str,
        text_outputs: Optional[Dict[str, str]] = None,
        image_ids: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a complete session summary.

        Args:
            mode_name: Mode that was played
            text_outputs: Dict of output type -> text content
            image_ids: List of image log IDs generated in session
            metadata: Additional session data

        Returns:
            Session log ID
        """
        try:
            entry_id = self._generate_id()
            day_dir = self._get_day_dir()

            session_entry = {
                "id": entry_id,
                "timestamp": datetime.now().isoformat(),
                "mode": mode_name,
                "text_outputs": text_outputs or {},
                "image_ids": image_ids or [],
                "metadata": metadata or {},
            }

            filename = f"session_{mode_name}_{entry_id}.json"
            filepath = day_dir / "metadata" / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_entry, f, ensure_ascii=False, indent=2)

            logger.info(f"Logged session summary: {filepath}")
            return entry_id

        except Exception as e:
            logger.error(f"Failed to log session summary: {e}")
            return ""


# Singleton accessor
_ai_logger: Optional[AILogger] = None


def get_ai_logger(log_dir: Optional[str] = None) -> AILogger:
    """Get the singleton AILogger instance."""
    global _ai_logger
    if _ai_logger is None:
        _ai_logger = AILogger(log_dir)
    return _ai_logger
