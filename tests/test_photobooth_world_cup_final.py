import asyncio
import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
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


def test_world_cup_final_theme_and_original_emblem_are_registered() -> None:
    theme = THEMES["world-cup-final"]
    assert theme.event_name == "WORLD CUP 2026"
    assert theme.event_date == "19.07"
    assert theme.ai_style_key == "world_cup_final"
    assert theme.description == "SPAIN × ARGENTINA"
    assert theme.theme_chrome == (117, 200, 245)
    assert theme.theme_red == (229, 41, 47)
    assert theme.theme_black == (7, 21, 47)
    assert theme.ticker_color == (244, 197, 66)

    emblem_path = Path(__file__).resolve().parents[1] / "assets" / "images" / theme.logo_filename
    emblem = Image.open(emblem_path)
    assert emblem.mode == "RGBA"
    assert emblem.size[0] == emblem.size[1]
    assert emblem.getchannel("A").getpixel((0, 0)) == 0


def test_world_cup_final_idle_uses_branded_2d_emblem_frame(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_THEME", "world-cup-final")
    manager = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    manager._theme = THEMES["world-cup-final"]
    assert manager._detect_idle_variant() == "world_cup_final"

    manager.idle_variant = "world_cup_final"
    manager._pil_available = True
    manager.cringe_assets = {}
    manager._load_cringe_party_assets()
    assert manager._build_idle_scene_playlist() == [IdleScene.CRINGE_HERO]
    assert manager._build_variant_scene_titles()[IdleScene.CRINGE_HERO] == "WORLD CUP 2026"
    assert manager.cringe_assets[IdleScene.CRINGE_HERO][0].shape == (160, 160, 3)


def test_world_cup_final_menu_mode_and_style_mapping(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "world_cup_final")
    modes = get_configured_photobooth_modes()
    assert len(modes) == 1
    assert modes[0].theme_id_override == "world-cup-final"

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode.ai_style_key_override = None
    mode._theme = THEMES["world-cup-final"]
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_WORLD_CUP_FINAL_SQUARE,
        CaricatureStyle.PHOTOBOOTH_WORLD_CUP_FINAL,
    )


def test_world_cup_final_prompt_is_likeness_first_flat_2d_and_9_16(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_WORLD_CUP_FINAL,
            prompt_variation_index=0,
        )
    )

    call = fake_client.calls[0]
    prompt = call["prompt"].lower()
    assert call["aspect_ratio"] == "9:16"
    assert "non-negotiable identity lock" in prompt
    assert "fixed underdrawing" in prompt
    assert "inter-eye distance" in prompt
    assert "include each real person exactly once" in prompt
    assert "do not replace their clothes with football kits" in prompt
    assert "premium hand-drawn flat 2d" in prompt
    assert "geometric floodlights" in prompt
    assert "controlled halftone crowd" in prompt
    assert "no official fifa" in prompt
    assert "no dead blank sky" in prompt
    assert "no empty footer band" in prompt
    assert "no generated text" in call["style"].lower()


def test_world_cup_final_branding_is_compact_and_full_bleed() -> None:
    source = Image.new("RGB", (768, 1365), (14, 86, 120))
    for y in range(source.height):
        source.putpixel((0, y), (14, y % 255, 120))
        source.putpixel((source.width - 1, y), (14, y % 255, 120))
    buf = io.BytesIO()
    source.save(buf, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["world-cup-final"]
    branded = mode._stamp_world_cup_final_logo(buf.getvalue())
    result = Image.open(
        io.BytesIO(mode._stamp_world_cup_final_footer(branded, "ВОСКРЕСЕНЬЕ", "22:30"))
    ).convert("RGB")

    assert result.size == source.size
    assert result.getpixel((0, result.height - 1)) == source.getpixel((0, source.height - 1))
    assert result.getpixel((result.width - 1, result.height - 1)) == source.getpixel(
        (source.width - 1, source.height - 1)
    )
    assert result.getpixel((result.width // 2, 70)) != source.getpixel((source.width // 2, 70))
    assert result.getpixel((result.width // 2, result.height - 90)) != source.getpixel(
        (source.width // 2, source.height - 90)
    )
