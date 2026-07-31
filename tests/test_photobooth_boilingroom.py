import asyncio
import base64
import hashlib
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import (
    PhotoboothMode,
    get_configured_photobooth_modes,
    get_moscow_party_stamp,
)
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)
CANONICAL_EMBLEM_SHA256 = (
    "d0e7cfe95790cfa0d8dd31d5b58be04d192528f772e87aa84662c3da963ea3ea"
)


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_boilingroom_theme_is_evergreen_and_uses_canonical_emblem() -> None:
    theme = THEMES["boilingroom"]
    assert theme.event_name == "BOILING ROOM"
    assert theme.event_date == ""
    assert theme.footer_date_mode == "weekday_ru"
    assert theme.party_date_rollover_hour == 12
    assert theme.menu_display_name == "BOILING\nROOM"
    assert theme.ticker_idle_cycle == ("BOILING", "ROOM")
    assert theme.reference_image_filenames == ("boilingroom.png",)
    assert theme.required_reference_sha256 == CANONICAL_EMBLEM_SHA256

    emblem_path = ROOT / "assets" / "images" / "boilingroom.png"
    assert hashlib.sha256(emblem_path.read_bytes()).hexdigest() == CANONICAL_EMBLEM_SHA256

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = theme
    mode._load_logo()
    assert len(mode._theme_reference_images) == 1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == CANONICAL_EMBLEM_SHA256


def test_boilingroom_uses_current_menu_and_dedicated_idle(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "boilingroom")
    modes = get_configured_photobooth_modes()
    assert len(modes) == 1
    assert modes[0].theme_id_override == "boilingroom"

    monkeypatch.setenv("PHOTOBOOTH_THEME", "boilingroom")
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES["boilingroom"]
    assert idle._detect_idle_variant() == "boilingroom"
    idle.idle_variant = "boilingroom"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_HERO]
    assert idle._build_variant_scene_titles() == {IdleScene.CRINGE_HERO: "BOILING ROOM"}

    idle._pil_available = True
    idle.cringe_assets = {}
    idle._load_cringe_party_assets()
    assert len(idle.cringe_assets[IdleScene.CRINGE_HERO]) == 1


def test_boilingroom_party_weekday_rolls_after_noon() -> None:
    theme = THEMES["boilingroom"]
    moscow = timezone(timedelta(hours=3))
    friday_night = datetime(2026, 8, 1, 3, 15, tzinfo=moscow)
    saturday_day = datetime(2026, 8, 1, 12, 0, tzinfo=moscow)
    assert get_moscow_party_stamp(theme, friday_night) == ("ПЯТНИЦА", "03:15")
    assert get_moscow_party_stamp(theme, saturday_day) == ("СУББОТА", "12:00")


def test_boilingroom_prompt_keeps_2d_style_and_locks_faces(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH,
            extra_reference_images=[(PNG_1X1, "image/png")],
            prompt_variation_index=0,
        )
    )

    call = fake_client.calls[0]
    prompt = call["prompt"].lower()
    assert call["aspect_ratio"] == "9:16"
    assert "fixed underdrawing" in prompt
    assert "inter-eye distance" in prompt
    assert "never duplicate or omit" in prompt
    assert "canonical boiling room chrome-ring emblem" in prompt
    assert "images 3 and later" in prompt
    assert "they are not extra people" in prompt
    assert "only readable text" in prompt
    assert "strictly a drawn / illustrated image" in prompt
    assert "not photorealistic, not 3d" in prompt
    assert "visible venue background as fixed underdrawings" in prompt
    assert "preserve the recognizable real venue background" in prompt
    assert "at least 65%" in prompt
    assert "no crushed black void" in prompt
    assert "instead of inventing a generic club" in prompt
    assert "no dates, times, address" in prompt
    assert "empty footer bar" in prompt
    assert "27.03" not in prompt


def test_boilingroom_footer_is_compact_and_preserves_full_bleed_edges() -> None:
    source = Image.new("RGB", (768, 1365), (80, 12, 18))
    for y in range(source.height):
        source.putpixel((0, y), (80, y % 255, 18))
        source.putpixel((source.width - 1, y), (80, y % 255, 18))
    buf = io.BytesIO()
    source.save(buf, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    result = Image.open(
        io.BytesIO(mode._stamp_boilingroom_footer(buf.getvalue(), "ПЯТНИЦА", "23:45"))
    ).convert("RGB")

    assert result.size == source.size
    assert result.getpixel((0, result.height - 40)) == source.getpixel((0, source.height - 40))
    assert result.getpixel((result.width - 1, result.height - 40)) == source.getpixel(
        (source.width - 1, source.height - 40)
    )
    assert result.getpixel((result.width // 2, result.height - 80)) != source.getpixel(
        (source.width // 2, source.height - 80)
    )


def test_boilingroom_activation_disables_historical_auto_reactivation() -> None:
    script = (ROOT / "scripts" / "activate-boilingroom-photobooth.sh").read_text()
    assert "set_env PHOTOBOOTH_THEME boilingroom" in script
    assert "set_env PHOTOBOOTH_MENU_MODES boilingroom" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_BOILINGROOM 1" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_WORLD_CUP_FINAL 0" in script

    autopull = (ROOT / "scripts" / "autopull.sh").read_text()
    assert 'ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS:-0' in autopull
    assert 'ARTIFACT_AUTO_ACTIVATE_BOILINGROOM:-1' in autopull
    assert "202607311200" in autopull
    assert "202608031200" in autopull
