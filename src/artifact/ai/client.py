"""Gemini API client singleton for VNVNC.

Based on patterns from voicio/gemini_client.py with adaptations for
arcade fortune-telling use case.
"""

import asyncio
import logging
import mimetypes
import os
from typing import Optional, Dict, Any, List, Union, Tuple
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

    # Image generation - Nano Banana 2
    FLASH_IMAGE_31 = "gemini-3.1-flash-image-preview"

    # Image generation - Nano Banana
    FLASH_IMAGE = "gemini-2.5-flash-image"

    # Image generation - Nano Banana Pro
    PRO_IMAGE = "gemini-3-pro-image-preview"

    # Legacy alias for backward compatibility
    IMAGEN = "gemini-3-pro-image-preview"


IMAGE_GENERATION_MODEL_ENV = "GEMINI_IMAGE_MODEL"
IMAGE_GENERATION_PROVIDER_ENV = "ARTIFACT_IMAGE_PROVIDER"
OPENROUTER_FALLBACK_ENV = "ARTIFACT_ENABLE_OPENROUTER_FALLBACK"
DEFAULT_IMAGE_GENERATION_MODEL = GeminiModel.PRO_IMAGE.value
VALID_IMAGE_GENERATION_MODELS = {
    GeminiModel.FLASH_IMAGE_31.value,
    GeminiModel.FLASH_IMAGE.value,
    GeminiModel.PRO_IMAGE.value,
}


@dataclass
class GeminiConfig:
    """Configuration for Gemini client."""

    api_key: str
    provider: str = "gemini"
    project: Optional[str] = None
    location: str = "global"
    timeout: float = 60.0  # 60 second timeout
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
            api_key = self._read_api_key_from_env()
            if not api_key:
                logger.warning("Gemini/Vertex API key not set, AI features will be disabled")
            config = self._build_config(api_key)

        self.config = config
        self._client = None  # Default client (v1)
        self._client_beta = None  # v1beta client for image generation
        self._vertex_token: Optional[str] = None
        self._vertex_token_expiry: float = 0.0
        self._initialized = True
        self._image_generation_model = self._resolve_image_generation_model()
        self._openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self._openrouter_image_model = os.environ.get(
            "OPENROUTER_IMAGE_MODEL",
            "google/gemini-3.1-flash-image-preview",
        ).strip()
        self._image_generation_provider = self._resolve_image_generation_provider()
        self._allow_openrouter_fallback = os.environ.get(OPENROUTER_FALLBACK_ENV, "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Build list of API keys for rotation on errors
        # Priority: GEMINI_API_KEYS (comma-separated) > individual env vars
        keys_csv = os.environ.get("GEMINI_API_KEYS", "")
        if keys_csv:
            self._api_keys = [k.strip() for k in keys_csv.split(",") if k.strip()]
        else:
            self._api_keys = [k for k in [
                self._raw_api_key_for_config(config),
                os.environ.get("GEMINI_API_KEY_2", ""),
                os.environ.get("GEMINI_API_KEY_3", ""),
                os.environ.get("GEMINI_API_KEY_BACKUP", ""),
            ] if k]
        self._current_key_index = 0
        # Ensure config uses the first key
        if self._api_keys and not config.api_key:
            self.config = self._build_config(self._api_keys[0])

        logger.info(
            "GeminiClient initialized (%s API key(s), provider=%s, image model=%s)",
            len(self._api_keys),
            self._image_generation_provider,
            self._image_generation_model,
        )

    @staticmethod
    def _read_api_key_from_env() -> str:
        for env_name in (
            "VERTEX_GEMINI_API_KEY",
            "VERTEX_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
        ):
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _parse_key_descriptor(raw_key: str) -> Dict[str, Optional[str]]:
        key = raw_key.strip()
        if not key.startswith("vertex:"):
            return {
                "provider": "gemini",
                "project": os.environ.get("GOOGLE_CLOUD_PROJECT") or None,
                "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
                "api_key": key,
            }

        parts = key.split(":")
        if len(parts) < 4:
            logger.error("Invalid Vertex key descriptor. Use vertex:PROJECT_ID:LOCATION:API_KEY")
            return {"provider": "vertex", "project": None, "location": "global", "api_key": ""}

        return {
            "provider": "vertex",
            "project": parts[1].strip() or None,
            "location": parts[2].strip() or "global",
            "api_key": ":".join(parts[3:]).strip(),
        }

    def _build_config(self, raw_key: str) -> GeminiConfig:
        parsed = self._parse_key_descriptor(raw_key)
        provider = os.environ.get("ARTIFACT_GEMINI_PROVIDER", parsed["provider"] or "gemini").strip().lower()
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes", "on"}:
            provider = "vertex"

        return GeminiConfig(
            api_key=parsed["api_key"] or "",
            provider=provider,
            project=parsed["project"] or os.environ.get("GOOGLE_CLOUD_PROJECT") or None,
            location=parsed["location"] or os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )

    @staticmethod
    def _raw_api_key_for_config(config: GeminiConfig) -> str:
        if config.provider == "vertex" and config.project:
            return f"vertex:{config.project}:{config.location}:{config.api_key}"
        return config.api_key

    def _resolve_image_generation_provider(self) -> str:
        configured = os.environ.get(IMAGE_GENERATION_PROVIDER_ENV, "").strip().lower()
        if configured:
            return configured
        if self.config.provider == "vertex":
            return "vertex"
        return "gemini"

    def _resolve_image_generation_model(self) -> str:
        """Resolve the active image generation model from the environment."""
        configured_model = os.environ.get(IMAGE_GENERATION_MODEL_ENV, "").strip()
        if not configured_model:
            return DEFAULT_IMAGE_GENERATION_MODEL

        if configured_model not in VALID_IMAGE_GENERATION_MODELS:
            logger.warning(
                "Unsupported %s=%s, falling back to %s",
                IMAGE_GENERATION_MODEL_ENV,
                configured_model,
                DEFAULT_IMAGE_GENERATION_MODEL,
            )
            return DEFAULT_IMAGE_GENERATION_MODEL

        return configured_model

    def _rotate_api_key(self) -> bool:
        """Rotate to next API key on 429 errors. Returns True if rotated."""
        if len(self._api_keys) <= 1:
            return False
        self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
        new_key = self._api_keys[self._current_key_index]
        parsed_config = self._build_config(new_key)
        self.config = GeminiConfig(
            api_key=parsed_config.api_key,
            provider=parsed_config.provider,
            project=parsed_config.project,
            location=parsed_config.location,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
            thinking_budget=self.config.thinking_budget,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
        )
        # Force client re-initialization with new key
        self._client = None
        self._client_beta = None
        logger.info(f"Rotated to API key {self._current_key_index + 1}/{len(self._api_keys)}")
        return True

    def _vertex_endpoint(self, model: str, api_version: str = "v1") -> str:
        if not self.config.project:
            raise ValueError("Vertex provider requires a Google Cloud project")
        return (
            f"https://aiplatform.googleapis.com/{api_version}/"
            f"projects/{self.config.project}/locations/{self.config.location}/"
            f"publishers/google/models/{model}:generateContent"
        )

    def _get_vertex_access_token(self) -> str:
        """Return a cached Google Cloud OAuth token for Vertex AI."""
        import time

        if self._vertex_token and time.time() < self._vertex_token_expiry - 60:
            return self._vertex_token

        # artifact.service runs as root on the Pi, but the ADC login used for
        # Vertex is owned by kirniy. Point google-auth at that Cloud SDK config
        # unless an explicit credentials path/config was already provided.
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("CLOUDSDK_CONFIG"):
            adc_config_dir = "/home/kirniy/.config/gcloud"
            adc_path = os.path.join(adc_config_dir, "application_default_credentials.json")
            if os.path.exists(adc_path):
                os.environ["CLOUDSDK_CONFIG"] = adc_config_dir

        import google.auth
        from google.auth.transport.requests import Request

        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        token = credentials.token
        if not token:
            raise RuntimeError("Google ADC did not return an access token")

        expiry = getattr(credentials, "expiry", None)
        self._vertex_token = token
        self._vertex_token_expiry = expiry.timestamp() if expiry else time.time() + 3000
        if project and not self.config.project:
            self.config.project = project
        return token

    def _auth_headers(self, api_key: str) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.provider == "vertex":
            if api_key:
                headers["x-goog-api-key"] = api_key
            else:
                headers["Authorization"] = f"Bearer {self._get_vertex_access_token()}"
        else:
            headers["x-goog-api-key"] = api_key
        return headers

    async def _post_generate_content_rest(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        api_key: str,
        timeout_multiplier: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        import aiohttp

        session_kwargs: Dict[str, Any] = {"trust_env": True}
        gemini_proxy = os.environ.get("GEMINI_PROXY", "").strip()
        if gemini_proxy and "generativelanguage.googleapis.com" in endpoint:
            try:
                from aiohttp_socks import ProxyConnector

                session_kwargs["connector"] = ProxyConnector.from_url(gemini_proxy)
                session_kwargs["trust_env"] = False
            except Exception as proxy_error:
                logger.warning("GEMINI_PROXY is set but could not be used: %s", proxy_error)

        async with aiohttp.ClientSession(**session_kwargs) as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=self._auth_headers(api_key),
                timeout=aiohttp.ClientTimeout(total=self.config.timeout * timeout_multiplier),
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise RuntimeError(f"API error {response.status}: {error_text}")
                return await response.json()

    @staticmethod
    def _extract_text_response(data: Dict[str, Any]) -> Optional[str]:
        for candidate in data.get("candidates", []) or []:
            for part in (candidate.get("content") or {}).get("parts", []) or []:
                text = part.get("text")
                if text:
                    return text
        return None

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
        image_data: Optional[bytes] = None,
        image_mime_type: str = "image/jpeg",
    ) -> Optional[str]:
        """Generate text using Gemini, optionally with an image.

        Args:
            prompt: The user prompt
            model: Which Gemini model to use (FLASH_3 is multimodal)
            system_instruction: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override max output tokens
            image_data: Optional image bytes for multimodal generation
            image_mime_type: MIME type of image (default: image/jpeg)

        Returns:
            Generated text or None on error
        """
        if self.config.provider == "vertex":
            return await self._generate_text_vertex(
                prompt=prompt,
                model=model,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
                image_data=image_data,
                image_mime_type=image_mime_type,
            )

        if not await self._ensure_client():
            return None

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature or self.config.temperature,
                max_output_tokens=max_tokens or self.config.max_output_tokens,
                system_instruction=system_instruction,
            )

            # Build contents - text only or multimodal
            if image_data:
                contents = [
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_data, mime_type=image_mime_type),
                ]
            else:
                contents = prompt

            # Generate with retry logic
            max_attempts = max(self.config.max_retries, len(self._api_keys))
            for attempt in range(max_attempts):
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
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err or "403" in err:
                        if self._rotate_api_key():
                            logger.info(f"Retrying text gen with key {self._current_key_index + 1}/{len(self._api_keys)}")
                            self._client = None
                            await self._ensure_client("v1")
                            await asyncio.sleep(self.config.retry_delay)
                            continue
                    if "503" in err or "overloaded" in err.lower():
                        logger.warning(f"Service overloaded, retry {attempt + 1}")
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    else:
                        raise

            logger.error("All retries exhausted")
            return None

        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return None

    async def _generate_text_vertex(
        self,
        prompt: str,
        model: GeminiModel,
        system_instruction: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        image_data: Optional[bytes],
        image_mime_type: str,
    ) -> Optional[str]:
        try:
            import base64

            parts: List[Dict[str, Any]] = [{"text": prompt}]
            if image_data:
                parts.append({
                    "inlineData": {
                        "mimeType": image_mime_type,
                        "data": base64.b64encode(image_data).decode("utf-8"),
                    }
                })
            payload: Dict[str, Any] = {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {
                    "temperature": temperature or self.config.temperature,
                    "maxOutputTokens": max_tokens or self.config.max_output_tokens,
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            max_attempts = max(self.config.max_retries, len(self._api_keys))
            for attempt in range(max_attempts):
                try:
                    data = await self._post_generate_content_rest(
                        self._vertex_endpoint(model.value, "v1"),
                        payload,
                        self.config.api_key,
                    )
                    if data:
                        text = self._extract_text_response(data)
                        if text:
                            return text
                except Exception as e:
                    err = str(e)
                    if ("429" in err or "RESOURCE_EXHAUSTED" in err or "403" in err) and self._rotate_api_key():
                        await asyncio.sleep(self.config.retry_delay)
                        continue
                    if "503" in err or "overloaded" in err.lower():
                        await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                        continue
                    raise
            return None
        except Exception as e:
            logger.error("Vertex text generation failed: %s", e)
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
        if self.config.provider == "vertex":
            return await self._generate_text_vertex(
                prompt=prompt,
                model=model,
                system_instruction=system_instruction,
                temperature=None,
                max_tokens=None,
                image_data=image_data,
                image_mime_type=mime_type,
            )

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

            max_attempts = max(self.config.max_retries, len(self._api_keys))
            for attempt in range(max_attempts):
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
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err or "403" in err:
                        if self._rotate_api_key():
                            logger.info(f"Retrying vision with key {self._current_key_index + 1}/{len(self._api_keys)}")
                            self._client = None
                            await self._ensure_client("v1")
                            await asyncio.sleep(self.config.retry_delay)
                            continue
                    if "503" in err or "overloaded" in err.lower():
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
        extra_reference_images: Optional[List[Tuple[bytes, str]]] = None,
    ) -> Optional[bytes]:
        """Generate an image using the configured Gemini image model.

        Can optionally take a reference photo to generate personalized
        caricatures or styled portraits.

        Args:
            prompt: Description of the image to generate
            reference_photo: Optional photo bytes to use as reference
            photo_mime_type: MIME type of reference photo
            aspect_ratio: Image aspect ratio (1:1, 9:16, 16:9, etc.)
            image_size: Output resolution ("1K", "2K", or "4K")
            style: Optional style guidance
            extra_reference_images: Additional non-subject reference images
                such as logos, emblems, or style anchors

        Returns:
            Image bytes (PNG) or None on error
        """
        if (
            not self.config.api_key
            and self._image_generation_provider not in {"openrouter", "vertex"}
        ):
            logger.error("Cannot generate image: no Gemini API key")
            return None
        if self._image_generation_provider == "vertex" and not self.config.project:
            logger.error("Cannot generate image: Vertex provider requires GOOGLE_CLOUD_PROJECT")
            return None
        if self._image_generation_provider == "openrouter" and not self._openrouter_api_key:
            logger.error("Cannot generate image: ARTIFACT_IMAGE_PROVIDER=openrouter but OPENROUTER_API_KEY is not set")
            return None

        try:
            import base64
            import aiohttp

            # Build the full prompt with style if provided
            full_prompt = prompt
            if style:
                full_prompt = f"{style}. {prompt}"
            if extra_reference_images:
                logger.info("Image generation request includes %d extra reference image(s)", len(extra_reference_images))

            if self._image_generation_provider == "openrouter":
                logger.info("Using OpenRouter as primary image generation provider")
                return await self._generate_image_openrouter_fallback(
                    full_prompt,
                    reference_photo,
                    photo_mime_type,
                    aspect_ratio,
                    image_size,
                    extra_reference_images,
                )

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

            if extra_reference_images:
                for image_bytes, mime_hint in extra_reference_images:
                    if not image_bytes:
                        continue
                    mime_type = mime_hint
                    if "/" not in mime_type:
                        guessed_mime, _ = mimetypes.guess_type(mime_type)
                        mime_type = guessed_mime or "image/png"
                    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                    parts.append({
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": image_b64,
                        }
                    })

            # Build request payload for the active Gemini image generation model
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

            image_model = self._image_generation_model

            if self._image_generation_provider == "vertex":
                endpoint = self._vertex_endpoint(image_model, "v1")
            else:
                endpoint = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{image_model}:generateContent"
                    f"?key={self.config.api_key}"
                )

            # Save reference photo immediately before any API attempts
            # so it is preserved even if generation fails
            if reference_photo:
                try:
                    get_ai_logger().save_reference_photo(reference_photo)
                except Exception:
                    pass

            max_attempts = max(self.config.max_retries, len(self._api_keys))
            for attempt in range(max_attempts):
                try:
                    async with aiohttp.ClientSession(trust_env=self._image_generation_provider != "vertex") as session:
                        async with session.post(
                            endpoint,
                            json=payload,
                            headers=self._auth_headers(self.config.api_key),
                            timeout=aiohttp.ClientTimeout(total=self.config.timeout * 2),
                        ) as response:
                            if response.status == 503:
                                logger.warning(f"Service unavailable, retry {attempt + 1}")
                                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                                continue

                            if not response.ok:
                                error_text = await response.text()
                                logger.error(f"API error {response.status}: {error_text}")
                                if (
                                    self._allow_openrouter_fallback
                                    and response.status in (429, 403, 401, 400)
                                    and attempt == max_attempts - 1
                                ):
                                    fallback = await self._generate_image_openrouter_fallback(
                                        full_prompt,
                                        reference_photo,
                                        photo_mime_type,
                                        aspect_ratio,
                                        image_size,
                                        extra_reference_images,
                                    )
                                    if fallback:
                                        return fallback
                                if response.status in (429, 403) and self._rotate_api_key():
                                    logger.info("Retrying with backup API key")
                                    # Rebuild endpoint with new key
                                    if self._image_generation_provider == "vertex":
                                        endpoint = self._vertex_endpoint(image_model, "v1")
                                    else:
                                        endpoint = (
                                            f"https://generativelanguage.googleapis.com/v1beta/models/"
                                            f"{image_model}:generateContent"
                                            f"?key={self.config.api_key}"
                                        )
                                    await asyncio.sleep(self.config.retry_delay)
                                    continue
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
                                                    model=image_model,
                                                    style=style,
                                                    reference_photo=reference_photo,
                                                    metadata={
                                                        "aspect_ratio": aspect_ratio,
                                                        "image_size": image_size,
                                                        "extra_reference_image_count": len(extra_reference_images or []),
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

            if self._allow_openrouter_fallback:
                fallback = await self._generate_image_openrouter_fallback(
                    full_prompt,
                    reference_photo,
                    photo_mime_type,
                    aspect_ratio,
                    image_size,
                    extra_reference_images,
                )
                if fallback:
                    return fallback
            return None

        except Exception as e:
            logger.warning("Gemini image generation failed: %s", e)
            if self._allow_openrouter_fallback:
                return await self._generate_image_openrouter_fallback(
                    locals().get("full_prompt", prompt),
                    reference_photo,
                    photo_mime_type,
                    aspect_ratio,
                    image_size,
                    extra_reference_images,
                )
            return None


    async def _generate_image_openrouter_fallback(
        self,
        full_prompt: str,
        reference_photo: Optional[bytes],
        photo_mime_type: str,
        aspect_ratio: str,
        image_size: str,
        extra_reference_images: Optional[List[Tuple[bytes, str]]],
    ) -> Optional[bytes]:
        """Fallback image generation through OpenRouter image-capable chat completions."""
        if not self._openrouter_api_key:
            return None

        try:
            import base64
            import aiohttp

            content: List[Dict[str, Any]] = [{"type": "text", "text": full_prompt}]
            if reference_photo:
                photo_b64 = base64.b64encode(reference_photo).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{photo_mime_type};base64,{photo_b64}"},
                })
            if extra_reference_images:
                for image_bytes, mime_hint in extra_reference_images:
                    if not image_bytes:
                        continue
                    mime_type = mime_hint if "/" in mime_hint else (mimetypes.guess_type(mime_hint)[0] or "image/png")
                    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    })

            payload = {
                "model": self._openrouter_image_model,
                "messages": [{"role": "user", "content": content}],
                "modalities": ["image", "text"],
                "image_config": {"aspect_ratio": aspect_ratio, "image_size": "1K"},
            }
            # Do not inherit proxy environment for OpenRouter fallback. The Pi's
            # Gemini proxy can be stale/dead while direct OpenRouter remains reachable.
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://vnvnc.ru",
                        "X-Title": "ARTIFACT Photobooth",
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout * 2),
                ) as response:
                    if not response.ok:
                        logger.error("OpenRouter image fallback failed: HTTP %s: %s", response.status, (await response.text())[:500])
                        return None
                    data = await response.json()

            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            for image in message.get("images") or []:
                image_url = (image.get("image_url") or {}).get("url") or ""
                if image_url.startswith("data:image") and "," in image_url:
                    return base64.b64decode(image_url.split(",", 1)[1])
            logger.error("OpenRouter image fallback returned no images")
            return None
        except Exception as e:
            logger.error("OpenRouter image fallback error: %s", e)
            return None

    @property
    def is_available(self) -> bool:
        """Check if AI features are available."""
        if self.config.provider == "vertex":
            return bool(self.config.project)
        return bool(self.config.api_key)

    @property
    def image_generation_model(self) -> str:
        """Return the active Gemini image generation model."""
        return self._image_generation_model


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
