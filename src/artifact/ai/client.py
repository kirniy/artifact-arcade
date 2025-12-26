"""Gemini API client singleton for VNVNC.

Based on patterns from voicio/gemini_client.py with adaptations for
arcade fortune-telling use case.
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum

from artifact.ai.logging import get_ai_logger

logger = logging.getLogger(__name__)


class GeminiModel(Enum):
    """Available Gemini models."""

    # Text generation (predictions) - Gemini 2.5 Flash with thinking
    FLASH = "gemini-2.5-flash"

    # Gemini 3 Flash - latest and fastest (Dec 2025)
    FLASH_3 = "gemini-3-flash-preview"

    # Image understanding (photo analysis) - Gemini 2.5 Flash supports vision
    FLASH_VISION = "gemini-2.5-flash"

    # Image generation (caricatures/sketches) - Gemini 3.0 Pro Image Preview
    PRO_IMAGE = "gemini-3-pro-image-preview"

    # Legacy alias for backward compatibility
    IMAGEN = "gemini-3-pro-image-preview"


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
        self._client = None  # Default client (v1)
        self._client_beta = None  # v1beta client for image generation
        self._initialized = True

        logger.info("GeminiClient initialized")

    async def _ensure_client(self, api_version: str = "v1") -> bool:
        """Ensure the API client is initialized.

        Args:
            api_version: API version to use ('v1' or 'v1beta')
        """
        # Check if already initialized
        if api_version == "v1beta":
            if self._client_beta is not None:
                return True
        else:
            if self._client is not None:
                return True

        if not self.config.api_key:
            logger.error("Cannot initialize client: no API key")
            return False

        try:
            # Import google-genai SDK
            from google import genai

            if api_version == "v1beta":
                self._client_beta = genai.Client(
                    api_key=self.config.api_key,
                    http_options={'api_version': 'v1beta'}
                )
                logger.info("Gemini API client connected (v1beta)")
            else:
                self._client = genai.Client(api_key=self.config.api_key)
                logger.info("Gemini API client connected (v1)")
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
        model: GeminiModel = GeminiModel.FLASH,
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
                        # Log the generation
                        try:
                            ai_logger = get_ai_logger()
                            ai_logger.log_text_generation(
                                category="text_generation",
                                prompt=prompt,
                                response=response.text,
                                model=model.value,
                                metadata={"system_instruction": system_instruction}
                            )
                        except Exception as log_error:
                            logger.debug(f"Failed to log generation: {log_error}")
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
        model: GeminiModel = GeminiModel.FLASH_VISION,
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
                types.Part.from_text(text=prompt),
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
                        # Log the vision analysis
                        try:
                            ai_logger = get_ai_logger()
                            ai_logger.log_text_generation(
                                category="vision_analysis",
                                prompt=prompt,
                                response=response.text,
                                model=model.value,
                                metadata={
                                    "has_image": True,
                                    "mime_type": mime_type,
                                    "system_instruction": system_instruction
                                }
                            )
                        except Exception as log_error:
                            logger.debug(f"Failed to log vision analysis: {log_error}")
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
        reference_photo: Optional[bytes] = None,
        photo_mime_type: str = "image/jpeg",
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
        style: Optional[str] = None,
    ) -> Optional[bytes]:
        """Generate an image using Gemini 3 Pro Image Preview.

        Can optionally take a reference photo to generate personalized
        caricatures or styled portraits.

        Args:
            prompt: Description of the image to generate
            reference_photo: Optional photo bytes to use as reference
            photo_mime_type: MIME type of reference photo
            aspect_ratio: Image aspect ratio (1:1, 9:16, 16:9, etc.)
            image_size: Output resolution ("1K", "2K", or "4K")
            style: Optional style guidance

        Returns:
            Image bytes (PNG) or None on error
        """
        if not self.config.api_key:
            logger.error("Cannot generate image: no API key")
            return None

        try:
            import base64
            import aiohttp

            # Build the full prompt with style if provided
            full_prompt = prompt
            if style:
                full_prompt = f"{style}. {prompt}"

            # Build parts array
            parts = [{"text": full_prompt}]

            # Add reference photo if provided
            if reference_photo:
                photo_b64 = base64.b64encode(reference_photo).decode("utf-8")
                parts.append({
                    "inlineData": {
                        "mimeType": photo_mime_type,
                        "data": photo_b64,
                    }
                })

            # Build request payload for Gemini 3 Pro Image Preview
            # Uses REST API directly for better control
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": parts,
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {
                        "aspectRatio": aspect_ratio,
                        "imageSize": image_size,  # "1K", "2K", "4K"
                    },
                },
            }

            # REST API endpoint for Gemini 3 Pro Image Preview
            endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{GeminiModel.IMAGEN.value}:generateContent"
                f"?key={self.config.api_key}"
            )

            for attempt in range(self.config.max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            endpoint,
                            json=payload,
                            headers={
                                "Content-Type": "application/json",
                                "x-goog-api-key": self.config.api_key,
                            },
                            timeout=aiohttp.ClientTimeout(total=self.config.timeout * 2),
                        ) as response:
                            if response.status == 503:
                                logger.warning(f"Service unavailable, retry {attempt + 1}")
                                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                                continue

                            if not response.ok:
                                error_text = await response.text()
                                logger.error(f"API error {response.status}: {error_text}")
                                if attempt < self.config.max_retries - 1:
                                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                                    continue
                                return None

                            data = await response.json()

                            # Extract image from response
                            candidates = data.get("candidates", [])
                            if candidates:
                                content = candidates[0].get("content", {})
                                parts = content.get("parts", [])
                                for part in parts:
                                    inline_data = part.get("inlineData") or part.get("inline_data")
                                    if inline_data:
                                        image_data = inline_data.get("data")
                                        if image_data:
                                            decoded_image = base64.b64decode(image_data)
                                            # Log the image generation
                                            try:
                                                ai_logger = get_ai_logger()
                                                ai_logger.log_image_generation(
                                                    category="generated_image",
                                                    image_data=decoded_image,
                                                    prompt=full_prompt,
                                                    model=GeminiModel.IMAGEN.value,
                                                    style=style,
                                                    reference_photo=reference_photo,
                                                    metadata={
                                                        "aspect_ratio": aspect_ratio,
                                                        "image_size": image_size,
                                                    }
                                                )
                                            except Exception as log_error:
                                                logger.debug(f"Failed to log image: {log_error}")
                                            return decoded_image

                            logger.warning(f"No image in response, attempt {attempt + 1}")

                except asyncio.TimeoutError:
                    logger.warning(f"Image generation timeout, attempt {attempt + 1}")
                except Exception as e:
                    error_str = str(e).lower()
                    if "503" in error_str or "overloaded" in error_str:
                        logger.warning(f"Service overloaded, retry {attempt + 1}")
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
