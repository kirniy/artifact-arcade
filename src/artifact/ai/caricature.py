"""Caricature generation service using Gemini/Imagen.

Generates stylized caricature portraits based on user photos,
optimized for thermal printer output (black and white, high contrast).

Based on patterns from nano-banana-pro with adaptations for
arcade fortune-telling use case.
"""

import logging
import asyncio
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from artifact.ai.client import get_gemini_client

logger = logging.getLogger(__name__)


class CaricatureStyle(Enum):
    """Available caricature styles."""

    MYSTICAL = "mystical"      # Crystal ball, stars, mystical elements
    FORTUNE = "fortune"        # Classic fortune teller style
    SKETCH = "sketch"          # Simple black and white sketch
    CARTOON = "cartoon"        # Exaggerated cartoon style
    VINTAGE = "vintage"        # Old-timey carnival style


@dataclass
class Caricature:
    """A generated caricature."""

    image_data: bytes
    style: CaricatureStyle
    width: int
    height: int
    format: str = "png"


# Prompt templates for different caricature styles
# All prompts emphasize: caricature OF THIS PERSON, thick black outlines, pure white background
STYLE_PROMPTS = {
    CaricatureStyle.MYSTICAL: """
Create a caricature portrait OF THIS PERSON from the reference photo.
Black and white hand-drawn sketch style with THICK bold black outlines.
Pure white background, no shading or gradients.
Exaggerate their distinctive facial features in a fun, flattering way.
High contrast suitable for thermal printer.
""",

    CaricatureStyle.FORTUNE: """
Create a caricature portrait OF THIS PERSON from the reference photo.
Black and white hand-drawn style with THICK bold black outlines.
Pure white background, clean and simple.
Exaggerate their distinctive features in a charming way.
High contrast suitable for thermal receipt printer.
""",

    CaricatureStyle.SKETCH: """
Create a caricature portrait OF THIS PERSON from the reference photo.
Simple black and white line drawing with THICK bold outlines.
Pure white background, minimal detail.
Exaggerate their distinctive features in a friendly way.
High contrast suitable for thermal printer.
""",

    CaricatureStyle.CARTOON: """
Create a caricature portrait OF THIS PERSON from the reference photo.
Black and white cartoon style with THICK bold black outlines.
Pure white background, no grayscale.
Exaggerate their distinctive features in a fun comic style.
High contrast suitable for thermal printing.
""",

    CaricatureStyle.VINTAGE: """
Create a caricature portrait OF THIS PERSON from the reference photo.
Black and white hand-drawn illustration with THICK bold outlines.
Pure white background, clean lines.
Exaggerate their distinctive features in a charming vintage style.
High contrast suitable for thermal receipt printer.
""",
}

NEGATIVE_PROMPT = """
photorealistic, photograph, 3D render, grayscale gradients,
complex shading, detailed background, color, low contrast,
unflattering, ugly, scary, disturbing, offensive
"""


class CaricatureService:
    """Service for generating AI-powered caricatures."""

    def __init__(self):
        self._client = get_gemini_client()

    @property
    def is_available(self) -> bool:
        """Check if caricature service is available."""
        return self._client.is_available

    async def generate_caricature(
        self,
        reference_photo: bytes,
        style: CaricatureStyle = CaricatureStyle.MYSTICAL,
        size: Tuple[int, int] = (384, 384),
        personality_context: Optional[str] = None,
    ) -> Optional[Caricature]:
        """Generate a caricature based on a reference photo.

        Sends the photo directly to Gemini 3 Pro Image Preview which
        can generate styled images based on reference photos.

        Args:
            reference_photo: User's photo as bytes
            style: Caricature style to use
            size: Output size (width, height)
            personality_context: Optional personality traits from questions

        Returns:
            Caricature object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for caricature generation")
            return None

        try:
            # Build the caricature prompt
            style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

            # Build personality-aware prompt
            personality_hint = ""
            if personality_context:
                personality_hint = f"""
PERSONALITY INSIGHT (use to inform the caricature's expression/vibe):
{personality_context}

Express their personality through the caricature - confident people get confident poses,
introverts get gentle expressions, risk-takers get dynamic poses, etc.
"""

            prompt = f"""Create a caricature portrait OF THIS EXACT PERSON from the reference photo.

CRITICAL REQUIREMENTS:
- This must be a caricature of THE PERSON IN THE PHOTO - capture their likeness
- Exaggerate their distinctive facial features (nose, eyes, chin, hair, etc.)
- THICK bold black outlines only
- Pure white background - no shading, no gradients, no gray
- Black and white only - suitable for thermal receipt printer
{personality_hint}
Style: {style_prompt}

The result should be recognizable as THIS specific person, but as a fun caricature.
"""

            # Send photo directly to Gemini 3 Pro Image Preview
            # The model understands to use the photo as reference
            image_data = await self._client.generate_image(
                prompt=prompt,
                reference_photo=reference_photo,
                photo_mime_type="image/jpeg",
                aspect_ratio="1:1",
                image_size="1K",  # Use 1K resolution
                style="Black and white sketch caricature, hand-drawn style, high contrast",
            )

            if image_data:
                # Process for thermal printer
                processed = await self._process_for_printer(image_data, size)
                return Caricature(
                    image_data=processed,
                    style=style,
                    width=size[0],
                    height=size[1],
                    format="png",
                )

        except Exception as e:
            logger.error(f"Caricature generation failed: {e}")

        return None

    def _build_caricature_prompt(self, description: str, style: CaricatureStyle) -> str:
        """Build the full prompt for caricature generation.

        Args:
            description: Description of the person's features
            style: Caricature style

        Returns:
            Complete prompt string
        """
        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

        return f"""Create a caricature portrait based on this description:
{description}

Style requirements:
{style_prompt}

Important: The caricature should be friendly, fun, and suitable for all ages.
Output should be optimized for thermal printer (pure black and white, high contrast).
"""

    async def _process_for_printer(
        self,
        image_data: bytes,
        target_size: Tuple[int, int],
    ) -> bytes:
        """Process the generated image for thermal printer output.

        Converts to high-contrast black and white, resizes for printer.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions

        Returns:
            Processed image bytes
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(image_data))

            # Convert to grayscale
            img = img.convert("L")

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Apply threshold for pure black and white
            threshold = 128
            img = img.point(lambda p: 255 if p > threshold else 0, mode="1")

            # Convert back to grayscale for compatibility
            img = img.convert("L")

            # Save to bytes
            output = BytesIO()
            img.save(output, format="PNG", optimize=True)
            return output.getvalue()

        except ImportError:
            logger.warning("PIL not available, returning original image")
            return image_data
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return image_data

    async def generate_simple_caricature(
        self,
        style: CaricatureStyle = CaricatureStyle.SKETCH,
    ) -> Optional[Caricature]:
        """Generate a generic caricature without a reference photo.

        Useful for testing or when camera is unavailable.

        Args:
            style: Caricature style

        Returns:
            Caricature object or None on error
        """
        if not self._client.is_available:
            return None

        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

        prompt = f"""Create a caricature portrait of a friendly mystical fortune teller character with:
- Warm, welcoming expression
- Mysterious yet approachable eyes
- Slight knowing smile
- Perhaps a headscarf or mystical accessory

Style requirements:
{style_prompt}
"""

        try:
            image_data = await self._client.generate_image(
                prompt=prompt,
                aspect_ratio="1:1",
                image_size="1K",
                style="Black and white sketch caricature, hand-drawn style, high contrast",
            )

            if image_data:
                processed = await self._process_for_printer(image_data, (384, 384))
                return Caricature(
                    image_data=processed,
                    style=style,
                    width=384,
                    height=384,
                    format="png",
                )

        except Exception as e:
            logger.error(f"Simple caricature generation failed: {e}")

        return None
