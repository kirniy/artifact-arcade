import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.ai.client import GeminiClient, GeminiConfig
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_jara_theme_is_registered_with_all_brand_references() -> None:
    theme = THEMES["jara"]
    assert theme.event_name == "ЖАРА"
    assert theme.ai_style_key == "jara"
    assert theme.reference_image_filenames == (
        "jara.png",
        "jara-style-reference.png",
    )


def test_jara_menu_mode_and_style_mapping(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "jara")
    modes = get_configured_photobooth_modes()
    assert len(modes) == 1
    assert modes[0].theme_id_override == "jara"

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode.ai_style_key_override = None
    mode._theme = THEMES["jara"]
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_JARA_SQUARE,
        CaricatureStyle.PHOTOBOOTH_JARA,
    )


def test_jara_vertical_generation_uses_identity_prompt_and_9_16(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_JARA,
            prompt_variation_index=0,
        )
    )

    call = fake_client.calls[0]
    assert call["aspect_ratio"] == "9:16"
    assert "IDENTITY IS THE ABSOLUTE PRIORITY" in call["prompt"]
    assert "striped beach chairs" in call["prompt"].lower()
    assert "do not draw a foam cannon" in call["prompt"].lower()
    assert "nozzle" in call["prompt"].lower()
    assert "deep cobalt" in call["prompt"].lower()
    assert "never a flat cyan fill" in call["prompt"].lower()
    assert "do not render жара" in call["prompt"].lower()
    assert "flat 2D" in call["style"]


def test_vertex_authorization_key_is_used_without_adc() -> None:
    client = object.__new__(GeminiClient)
    client.config = GeminiConfig(
        api_key="secret-test-key",
        provider="vertex",
        project="test-project",
        location="global",
    )
    headers = client._auth_headers("secret-test-key")
    assert headers["x-goog-api-key"] == "secret-test-key"
    assert "Authorization" not in headers
