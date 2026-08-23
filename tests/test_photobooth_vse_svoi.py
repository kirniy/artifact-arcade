import asyncio
import base64
import hashlib
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)
PENDANT_SHA256 = "d2b2bbf4047b834bfb3bf1132048cbd64d0e38a89d8a689bb3280b719d47342a"


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_vse_svoi_theme_uses_exact_vnvnc_pendant_and_safe_ticker() -> None:
    theme = THEMES["vse-svoi"]
    assert theme.event_name == "ВСЕ СВОИ"
    assert theme.footer_date_mode == "weekday_ru"
    assert theme.ai_style_key == "vse_svoi"
    assert theme.ticker_idle_cycle == ("ВСЕ", "СВОИ", "ФОТОБУДКА")
    assert theme.ticker_color[0] == 0
    assert theme.logo_filename == "vnvnc-pendant.png"
    assert theme.reference_image_filenames == ("vnvnc-pendant.png",)
    assert theme.required_reference_sha256 == PENDANT_SHA256

    pendant = ROOT / "assets" / "images" / "vnvnc-pendant.png"
    assert hashlib.sha256(pendant.read_bytes()).hexdigest() == PENDANT_SHA256

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = theme
    mode._load_logo()
    assert len(mode._theme_reference_images) == 1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == PENDANT_SHA256


def test_vse_svoi_menu_style_and_idle_package(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "vse_svoi")
    modes = get_configured_photobooth_modes()
    assert len(modes) == 1
    assert modes[0].theme_id_override == "vse-svoi"

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode.ai_style_key_override = None
    mode._theme = THEMES["vse-svoi"]
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_VSE_SVOI_SQUARE,
        CaricatureStyle.PHOTOBOOTH_VSE_SVOI,
    )

    monkeypatch.setenv("PHOTOBOOTH_THEME", "vse-svoi")
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES["vse-svoi"]
    assert idle._detect_idle_variant() == "vse_svoi"
    idle.idle_variant = "vse_svoi"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_HERO]
    assert idle._build_variant_scene_titles() == {IdleScene.CRINGE_HERO: "ВСЕ СВОИ"}
    idle._pil_available = True
    idle.cringe_assets = {}
    idle._load_cringe_party_assets()
    assert len(idle.cringe_assets[IdleScene.CRINGE_HERO]) == 1


def test_vse_svoi_prompt_matches_boiling_style_and_requires_exact_pendants(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_VSE_SVOI,
            extra_reference_images=[(PNG_1X1, "image/png")],
            prompt_variation_index=0,
        )
    )

    call = fake_client.calls[0]
    prompt = call["prompt"].lower()
    assert call["aspect_ratio"] == "9:16"
    assert "current boiling room theme" in prompt
    assert "fixed underdrawings" in prompt
    assert "recognizable real venue" in prompt
    assert "exact identity outranks" in prompt
    assert "inter-eye distance" in prompt
    assert "at least 65%" in prompt
    assert "canonical silver vnvnc chain pendant" in prompt
    assert "exactly one pendant is allowed" in prompt
    assert "do not put any pendant" in prompt
    assert "vnvnc jewelry" in prompt
    assert "central top 38%" in prompt
    assert "no white caption panel" in prompt
    assert "prompt text" in prompt
    assert "no 3d" in prompt
    assert "vnvnc chain pendant" not in call["style"].lower()
    assert "no pendants, necklaces, chains" in call["style"]
    assert "one deterministic master pendant" in call["style"]


def test_vse_svoi_postprocess_preserves_light_artwork_and_adds_hero_pendant() -> None:
    source = Image.new("RGB", (900, 1600), (174, 113, 86))
    draw = ImageDraw.Draw(source)
    # This sustained neutral-light region used to be mistaken for a generated
    # caption panel. The repair then stretched a thin strip over the rest of the
    # image, producing the vertical smearing seen in real guest photos.
    draw.rectangle((0, 1080, 900, 1600), fill=(248, 246, 240))
    for x in range(0, 900, 36):
        draw.line((x, 1080, x + 90, 1600), fill=(120, 120, 120), width=2)
    encoded = io.BytesIO()
    source.save(encoded, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    result = Image.open(io.BytesIO(mode._stamp_vse_svoi_pendants(encoded.getvalue()))).convert(
        "RGB"
    )
    assert result.size == source.size
    # The exact metal hero pendant changes the previously flat top-center area.
    top_center = result.crop((260, 0, 640, 420))
    assert len(top_center.getcolors(maxcolors=1_000_000)) > 100
    # Outside the pendant, postprocessing must never rebuild or stretch artwork.
    assert result.crop((0, 700, 900, 1600)).tobytes() == source.crop(
        (0, 700, 900, 1600)
    ).tobytes()


def test_vse_svoi_overlay_does_not_blur_or_rebuild_background() -> None:
    source = Image.new("RGB", (900, 1600), "white")
    draw = ImageDraw.Draw(source)
    for y in range(0, 700, 8):
        draw.line((0, y, 900, y), fill=(220, 20, 20), width=2)
    for x in range(0, 900, 8):
        draw.line((x, 0, x, 700), fill=(20, 20, 220), width=2)
    encoded = io.BytesIO()
    source.save(encoded, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    result = Image.open(io.BytesIO(mode._stamp_vse_svoi_pendants(encoded.getvalue()))).convert(
        "RGB"
    )
    # Outside the hero pendant bounds, the sharp source pixels stay byte-identical.
    for point in ((20, 20), (120, 160), (760, 240), (870, 500)):
        assert result.getpixel(point) == source.getpixel(point)


def test_vse_svoi_activation_disables_expired_event_overrides() -> None:
    script = (ROOT / "scripts" / "activate-vse-svoi-photobooth.sh").read_text()
    assert "set_env PHOTOBOOTH_THEME vse-svoi" in script
    assert "set_env PHOTOBOOTH_MENU_MODES vse_svoi" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_BOILINGROOM 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_JARA 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_WORLD_CUP_FINAL 0" in script
