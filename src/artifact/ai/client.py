"""Gemini API client singleton for ARTIFACT.

Based on patterns from voicio/gemini_client.py with adaptations for
arcade fortune-telling use case.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GeminiModel(Enum):
    """Available Gemini models."""

    # Text generation (predictions)
    FLASH_2_5 = "gemini-2.5-flash-preview-05-20"

    # Image generation (caricatures)
    PRO_IMAGE = "gemini-2.0-flash-exp"  # For image understanding
    IMAGEN = "imagen-3.0-generate-002"  # For image generation


@dataclass
class GeminiConfig:
    """Configuration for Gemini client."""

    api_key: str
    timeout: float = 300.0  # 5 minute timeout
    max_retries: int = 3
    retry_delay: float = 1.0
    thinking_budget: int = 1024  # Tokens for thinking
    temperature: float = 0.9  # Creative responses
    max_output_tokens: int = 2048


class GeminiClient:
    """Singleton Gemini API client.

    Provides async interface to Gemini models for:
    - Text predictions (2.5 Flash)
    - Image analysis (2.0 Flash)
    - Image generation (Imagen 3)
    """

    _instance: Optional["GeminiClient"] = None
    _initialized: bool = False

    def __new__(cls, config: Optional[GeminiConfig] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[GeminiConfig] = None):
        if self._initialized:
            return

        if config is None:
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                logger.warning("GEMINI_API_KEY not set, AI features will be disabled")
            config = GeminiConfig(api_key=api_key)

        self.config = config
        self._client = None
        self._initialized = True

        logger.info("GeminiClient initialized")

    async def _ensure_client(self) -> bool:
        """Ensure the API client is initialized."""
        if self._client is not None:
            return True

        if not self.config.api_key:
            logger.error("Cannot initialize client: no API key")
            return False

        try:
            # Import google-genai SDK
            from google import genai

            self._client = genai.Client(api_key=self.config.api_key)
            logger.info("Gemini API client connected")
            return True

        except ImportError:
            logger.error("google-genai package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            return False

    async def generate_text(
        self,
        prompt: str,
        model: GeminiModel = GeminiModel.FLASH_2_5,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Generate text using Gemini.

        Args:
            prompt: The user prompt
            model: Which Gemini model to use
            system_instruction: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override max output tokens

        Returns:
            Generated text or None on error
        """
        if not await self._ensure_client():
            return None

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature or self.config.temperature,
                max_output_tokens=max_tokens or self.config.max_output_tokens,
                system_instruction=system_instruction,
            )

            # Generate with retry logic
            for attempt in range(self.config.max_retries):
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self._client.models.generate_content,
                            model=model.value,
                            contents=prompt,
                            config=config,
                        ),
                        timeout=self.config.timeout,
                    )

                    if response and response.text:
                        return response.text

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on attempt {attempt + 1}")
                except Exception as e:
                    if "503" in str(e) or "overloaded" in str(e).lower():
                        logger.warning(f"Service overloaded, retry {attempt + 1}")
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        raise

            logger.error("All retries exhausted")
            return None

        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return None

    async def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        mime_type: str = "image/jpeg",
        model: GeminiModel = GeminiModel.PRO_IMAGE,
        system_instruction: Optional[str] = None,
    ) -> Optional[str]:
        """Generate text based on an image.

        Args:
            prompt: The user prompt describing what to analyze
            image_data: Raw image bytes
            mime_type: Image MIME type
            model: Which model to use
            system_instruction: Optional system prompt

        Returns:
            Generated text or None on error
        """
        if not await self._ensure_client():
            return None

        try:
            from google.genai import types
            import base64

            # Encode image to base64
            image_b64 = base64.b64encode(image_data).decode("utf-8")

            # Create multimodal content
            contents = [
                types.Part.from_text(prompt),
                types.Part.from_bytes(
                    data=image_data,
                    mime_type=mime_type,
                ),
            ]

            config = types.GenerateContentConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                system_instruction=system_instruction,
            )

            for attempt in range(self.config.max_retries):
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self._client.models.generate_content,
                            model=model.value,
                            contents=contents,
                            config=config,
                        ),
                        timeout=self.config.timeout,
                    )

                    if response and response.text:
                        return response.text

                except asyncio.TimeoutError:
                    logger.warning(f"Image analysis timeout, attempt {attempt + 1}")
                except Exception as e:
                    if "503" in str(e):
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        raise

            return None

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return None

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None,
    ) -> Optional[bytes]:
        """Generate an image using Imagen 3.

        Args:
            prompt: Description of the image to generate
            aspect_ratio: Image aspect ratio (1:1, 16:9, etc.)
            negative_prompt: What to avoid in the image

        Returns:
            Image bytes (PNG) or None on error
        """
        if not await self._ensure_client():
            return None

        try:
            from google.genai import types

            # Imagen 3 configuration
            config = types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
                output_mime_type="image/png",
            )

            for attempt in range(self.config.max_retries):
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self._client.models.generate_images,
                            model=GeminiModel.IMAGEN.value,
                            prompt=prompt,
                            config=config,
                        ),
                        timeout=self.config.timeout * 2,  # Longer timeout for images
                    )

                    if response and response.generated_images:
                        image = response.generated_images[0]
                        if hasattr(image, "image") and hasattr(image.image, "image_bytes"):
                            return image.image.image_bytes

                except asyncio.TimeoutError:
                    logger.warning(f"Image generation timeout, attempt {attempt + 1}")
                except Exception as e:
                    if "503" in str(e):
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        raise

            return None

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """Check if AI features are available."""
        return bool(self.config.api_key)


# Module-level singleton accessor
_client: Optional[GeminiClient] = None


def get_gemini_client(config: Optional[GeminiConfig] = None) -> GeminiClient:
    """Get the singleton Gemini client instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        GeminiClient singleton instance
    """
    global _client
    if _client is None:
        _client = GeminiClient(config)
    return _client
