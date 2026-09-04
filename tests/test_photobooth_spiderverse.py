import hashlib
import asyncio
import base64
from pathlib import Path

import pytest
from PIL import Image
import io

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode
from artifact.modes.photobooth_themes import get_theme_by_id


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)


def test_spiderverse_theme_package_is_complete(monkeypatch):
    theme = get_theme_by_id("spiderverse")
    emblem = ROOT / "assets/images/spiderverse-emblem.png"
    video = ROOT / "assets/idle/spiderverse/video/spiderverse-emo-dance.mp4"
    assert theme.ai_style_key == "spiderverse"
    assert theme.ticker_idle_cycle == ("SPIDER", "VERSE", "ФОТОБУДКА")
    assert theme.ticker_color == (0, 255, 48)
    assert theme.idle_video_required
    assert emblem.is_file() and video.is_file()
    assert hashlib.sha256(emblem.read_bytes()).hexdigest() == theme.required_reference_sha256

    monkeypatch.setenv("PHOTOBOOTH_THEME", "spiderverse")
    idle = RotatingIdleAnimation()
    assert idle.idle_variant == "spiderverse"
    assert idle.scenes == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle.cringe_circle_video_path == video


def test_spiderverse_mode_selects_dedicated_styles(monkeypatch):
    monkeypatch.setenv("PHOTOBOOTH_THEME", "spiderverse")
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode.ai_style_key_override = None
    mode._theme = get_theme_by_id("spiderverse")
    mode._load_logo()
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_SPIDERVERSE_SQUARE,
        CaricatureStyle.PHOTOBOOTH_SPIDERVERSE,
    )
    assert mode._theme_reference_images
    compressed, mime = mode._theme_reference_images[0]
    assert mime == "image/jpeg"
    assert len(compressed) < 300_000
    assert max(Image.open(io.BytesIO(compressed)).size) <= 1024


def test_spiderverse_prompt_is_identity_locked_and_brand_safe(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.is_available = True
            self.kwargs = None

        async def generate_image(self, **kwargs):
            self.kwargs = kwargs
            return PNG_1X1

    client = FakeClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"source-photo",
            style=CaricatureStyle.PHOTOBOOTH_SPIDERVERSE,
            extra_reference_images=[(PNG_1X1, "image/png"), (PNG_1X1, "image/png")],
            prompt_variation_index=0,
        )
    )
    prompt = client.kwargs["prompt"]
    lowered = prompt.lower()
    assert client.kwargs["aspect_ratio"] == "9:16"
    assert "fixed underdrawing" in lowered
    assert "recognizable actual venue" in lowered
    assert "image 2" in lowered and "exact canonical spiderverse" in lowered
    assert "dimensional cgi" in lowered and "halftone" in lowered
    assert "wardrobe override" in lowered
    assert "raised black web lattice" in lowered
    assert "no mask, hood, helmet" in lowered
    assert "from the neck down" in lowered
    assert "partial physical sign" in lowered
    assert "separate complete hero emblem" in lowered
    assert "spider-man" not in lowered
    assert "marvel" not in lowered
    assert "into the spider-verse" not in lowered


def test_spiderverse_footer_has_scarlet_suit_web_panel():
    source = Image.new("RGB", (768, 1365), (230, 220, 200))
    buf = io.BytesIO()
    source.save(buf, format="PNG")
    mode = PhotoboothMode.__new__(PhotoboothMode)
    result = Image.open(io.BytesIO(mode._stamp_spiderverse_footer(buf.getvalue(), "ПЯТНИЦА", "23:15"))).convert("RGB")
    assert result.size == source.size
    # Center of the compact card is unmistakably scarlet; its edge is navy.
    assert result.getpixel((384, 1225))[0] > result.getpixel((384, 1225))[2] * 2
    assert result.getpixel((28, 1225))[2] > result.getpixel((28, 1225))[0]
