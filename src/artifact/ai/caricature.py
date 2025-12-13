"""Caricature generation service using Gemini/Imagen.

Generates stylized caricature portraits based on user photos,
optimized for thermal printer output (black and white, high contrast).

Based on patterns from nano-banana-pro with adaptations for
arcade fortune-telling use case.
"""

import logging
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from artifact.ai.client import get_gemini_client, GeminiModel

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
STYLE_PROMPTS = {
    CaricatureStyle.MYSTICAL: """
Black and white sketch caricature portrait in mystical fortune teller style.
The subject should be surrounded by stars, moons, and cosmic elements.
Hand-drawn doodle style with bold outlines, high contrast for thermal printing.
Simple white background, no complex shading.
Exaggerated friendly features in whimsical style.
""",

    CaricatureStyle.FORTUNE: """
Black and white caricature portrait in vintage carnival fortune teller style.
Include subtle mystical elements like a crystal ball reflection or tarot symbols.
Hand-drawn sketch style with bold black lines on white background.
High contrast suitable for thermal receipt printer.
Friendly exaggerated features, not unflattering.
""",

    CaricatureStyle.SKETCH: """
Simple black and white line drawing caricature portrait.
Clean hand-drawn sketch style with minimal shading.
Bold outlines on pure white background.
High contrast suitable for thermal printer output.
Friendly caricature with exaggerated but flattering features.
""",

    CaricatureStyle.CARTOON: """
Black and white cartoon style caricature portrait.
Exaggerated friendly features in comic book style.
Bold black outlines, no grayscale, pure black and white.
Simple white background, high contrast for thermal printing.
Fun and whimsical, not realistic.
""",

    CaricatureStyle.VINTAGE: """
Black and white caricature portrait in vintage 1920s carnival style.
Hand-drawn illustration style with decorative border elements.
Bold lines, high contrast, no halftones.
White background suitable for thermal receipt printer.
Charming old-timey carnival atmosphere.
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
    ) -> Optional[Caricature]:
        """Generate a caricature based on a reference photo.

        Args:
            reference_photo: User's photo as bytes
            style: Caricature style to use
            size: Output size (width, height)

        Returns:
            Caricature object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for caricature generation")
            return None

        try:
            # First, analyze the photo to get a description
            description = await self._analyze_for_caricature(reference_photo)
            if not description:
                logger.error("Failed to analyze photo for caricature")
                return None

            # Build the caricature prompt
            prompt = self._build_caricature_prompt(description, style)

            # Generate the image
            image_data = await self._client.generate_image(
                prompt=prompt,
                aspect_ratio="1:1",
                negative_prompt=NEGATIVE_PROMPT,
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

    async def _analyze_for_caricature(self, photo: bytes) -> Optional[str]:
        """Analyze a photo to extract features for caricature.

        Args:
            photo: Photo bytes

        Returns:
            Description of features for caricature generation
        """
        prompt = """Describe this person's key facial features for creating a friendly caricature:
- Face shape (round, oval, square, etc.)
- Notable features to exaggerate (big smile, expressive eyes, etc.)
- Hair style and any distinctive elements
- Overall expression and energy

Keep it brief (2-3 sentences) and focus on features that make good caricatures.
Be positive and flattering in your descriptions."""

        try:
            response = await self._client.generate_with_image(
                prompt=prompt,
                image_data=photo,
                mime_type="image/jpeg",
                model=GeminiModel.PRO_IMAGE,
            )
            return response

        except Exception as e:
            logger.error(f"Photo analysis for caricature failed: {e}")
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

        generic_description = """
A friendly mystical fortune teller character with:
- Warm, welcoming expression
- Mysterious yet approachable eyes
- Slight knowing smile
- Perhaps a headscarf or mystical accessory
"""

        prompt = self._build_caricature_prompt(generic_description, style)

        try:
            image_data = await self._client.generate_image(
                prompt=prompt,
                aspect_ratio="1:1",
                negative_prompt=NEGATIVE_PROMPT,
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
