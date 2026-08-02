import asyncio
import base64
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)
CLASSIC_LOGO_SHA256 = "6608303c03fb0565f3c998e8cda85064303477edbb672f07e55a9b462ac79570"


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_vse_svoi_theme_uses_classic_vnvnc_logo_and_safe_ticker() -> None:
    theme = THEMES["vse-svoi"]
    assert theme.event_name == "ВСЕ СВОИ"
    assert theme.footer_date_mode == "weekday_ru"
    assert theme.ai_style_key == "vse_svoi"
    assert theme.ticker_idle_cycle == ("ВСЕ", "СВОИ", "ФОТОБУДКА")
    assert theme.ticker_color[0] == 0
    assert theme.reference_image_filenames == (
        "../logos/vnvnc-logo-classic-border-letters-black.png",
    )
    assert theme.required_reference_sha256 == CLASSIC_LOGO_SHA256

    logo = ROOT / "assets" / "logos" / "vnvnc-logo-classic-border-letters-black.png"
    assert hashlib.sha256(logo.read_bytes()).hexdigest() == CLASSIC_LOGO_SHA256

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = theme
    mode._load_logo()
    assert len(mode._theme_reference_images) == 1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == CLASSIC_LOGO_SHA256


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


def test_vse_svoi_prompt_matches_boiling_style_but_uses_classic_logo(monkeypatch) -> None:
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
    assert "vnvnc classic logo" in prompt
    assert "tall condensed latin vnvnc" in prompt
    assert "only readable text" in prompt
    assert "no все свои title inside the artwork" in prompt
    assert "no 3d" in prompt
    assert "VNVNC CLASSIC LOGO" in call["style"]


def test_vse_svoi_activation_disables_expired_event_overrides() -> None:
    script = (ROOT / "scripts" / "activate-vse-svoi-photobooth.sh").read_text()
    assert "set_env PHOTOBOOTH_THEME vse-svoi" in script
    assert "set_env PHOTOBOOTH_MENU_MODES vse_svoi" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_BOILINGROOM 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_JARA 0" in script
    assert "set_env ARTIFACT_AUTO_ACTIVATE_WORLD_CUP_FINAL 0" in script
