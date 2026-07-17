import asyncio
import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.ai.client import GeminiClient, GeminiConfig
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
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
    assert theme.theme_chrome == (255, 54, 35)
    assert theme.theme_red == (255, 86, 160)
    assert theme.theme_black == (4, 38, 82)
    assert theme.ticker_color == (0, 220, 255)


def test_jara_idle_uses_supplied_theme_video(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_THEME", "jara")
    manager = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    manager._theme = THEMES["jara"]

    assert manager._detect_idle_variant() == "jara"

    manager.idle_variant = "jara"
    manager.idle_title = "ЖАРА"
    manager.idle_lcd_prefix = "ЖАРА"
    manager.state = type("State", (), {"current_scene": IdleScene.CRINGE_CIRCLE_VIDEO, "scene_time": 0})()
    assert manager._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert manager._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "ЖАРА"
    assert manager.get_scene_name() == "ЖАРА"
    assert "ЖАРА" in manager.get_lcd_text()

    manager._cv2_available = True
    manager.cringe_circle_video_path = None
    manager._load_cringe_circle_video()
    assert manager.cringe_circle_video_path is not None
    assert manager.cringe_circle_video_path.name == "jara-fans.mp4"
    assert manager.cringe_circle_video_path.exists()


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
    assert "NON-NEGOTIABLE IDENTITY LOCK" in call["prompt"]
    assert "striped beach chairs" in call["prompt"].lower()
    assert "do not draw a foam cannon" in call["prompt"].lower()
    assert "nozzle" in call["prompt"].lower()
    assert "inter-eye distance" in call["prompt"].lower()
    assert "do not homogenize" in call["prompt"].lower()
    assert "no giant cumulus" in call["prompt"].lower()
    assert "full bleed" in call["prompt"].lower()
    assert "no empty cyan" in call["prompt"].lower()
    assert "do not render жара" in call["prompt"].lower()
    assert "High-fidelity 2D rotoscope" in call["style"]


def test_jara_footer_is_a_floating_card_not_a_full_width_bar() -> None:
    source = Image.new("RGB", (768, 1365), (12, 130, 210))
    for y in range(source.height):
        source.putpixel((0, y), (12, y % 255, 210))
        source.putpixel((source.width - 1, y), (12, y % 255, 210))
    buf = io.BytesIO()
    source.save(buf, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["jara"]
    result = Image.open(
        io.BytesIO(mode._stamp_jara_footer(buf.getvalue(), "ПЯТНИЦА", "19:43"))
    ).convert("RGB")

    assert result.size == source.size
    assert result.getpixel((0, result.height - 1)) == source.getpixel((0, source.height - 1))
    assert result.getpixel((result.width - 1, result.height - 1)) == source.getpixel(
        (source.width - 1, source.height - 1)
    )
    assert result.getpixel((result.width // 2, result.height - 90)) != source.getpixel(
        (source.width // 2, source.height - 90)
    )


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
