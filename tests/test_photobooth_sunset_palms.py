import asyncio
import base64
import hashlib
import inspect
import io
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)
CANONICAL_EMBLEM_SHA256 = "75da4849ac164cc099e1309933916fada4d718e3cd18a40edf204e6128f6a448"


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_sunset_palms_theme_and_canonical_emblem_are_registered() -> None:
    theme = THEMES["sunset-palms"]
    assert theme.event_name == "SUNSET PALMS"
    assert theme.ai_style_key == "sunset_palms"
    assert theme.description == "ФЕСТИВАЛЬ ЗАКАТА"
    assert theme.reference_image_filenames == ("sunset-palms-emblem.png",)
    assert theme.required_reference_sha256 == CANONICAL_EMBLEM_SHA256
    assert theme.idle_video_filename == "sunset-palms-fans.mp4"
    assert theme.idle_video_required is True
    assert theme.theme_chrome == (255, 177, 87)
    assert theme.theme_red == (242, 91, 117)
    assert theme.theme_black == (54, 27, 67)
    assert theme.ticker_color == (0, 255, 48)
    assert theme.ticker_color[0] == 0
    assert theme.ticker_compact_static is True
    assert theme.ticker_x_offset == 2
    assert theme.ticker_safe_left == 8
    assert theme.ticker_idle_cycle == ("SUNSET", "PALMS", "ФОТОБУДКА")

    emblem_path = ROOT / "assets" / "images" / theme.logo_filename
    assert hashlib.sha256(emblem_path.read_bytes()).hexdigest() == CANONICAL_EMBLEM_SHA256
    emblem = Image.open(emblem_path)
    assert emblem.mode == "RGBA"
    assert emblem.size == (1548, 1284)

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = theme
    mode._load_logo()
    assert len(mode._theme_reference_images) == 1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == CANONICAL_EMBLEM_SHA256


def test_sunset_palms_menu_style_and_idle_slot(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "sunset_palms")
    modes = get_configured_photobooth_modes()
    assert len(modes) == 1
    assert modes[0].theme_id_override == "sunset-palms"

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode.ai_style_key_override = None
    mode._theme = THEMES["sunset-palms"]
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_SUNSET_PALMS_SQUARE,
        CaricatureStyle.PHOTOBOOTH_SUNSET_PALMS,
    )

    monkeypatch.setenv("PHOTOBOOTH_THEME", "sunset-palms")
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES["sunset-palms"]
    assert idle._detect_idle_variant() == "sunset_palms"
    idle.idle_variant = "sunset_palms"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "SUNSET PALMS"


def test_sunset_ticker_keeps_full_height_and_first_s_off_left_seam() -> None:
    import numpy as np

    from artifact.graphics.text_utils import render_idle_style_ticker_text

    theme = THEMES["sunset-palms"]
    for text in theme.ticker_idle_cycle:
        buffer = np.zeros((8, 48, 3), dtype=np.uint8)
        render_idle_style_ticker_text(
            buffer,
            text,
            theme.ticker_color or theme.theme_chrome,
            0.0,
            compact_static=theme.ticker_compact_static,
            x_offset=theme.ticker_x_offset if text == theme.ticker_idle else 0,
            safe_left=theme.ticker_safe_left,
        )
        lit_columns = np.flatnonzero(buffer.any(axis=(0, 2)))
        lit_rows = np.flatnonzero(buffer.any(axis=(1, 2)))
        assert lit_rows.min() == 0, text
        assert lit_rows.max() == 6, text
        if text == "SUNSET":
            assert lit_columns.min() >= theme.ticker_safe_left
            assert lit_columns.max() < 48
        if text == "ФОТОБУДКА":
            assert lit_columns.min() >= theme.ticker_safe_left
            assert lit_columns.max() < 48
            # The Ф has a unique center stem before the О begins.
            assert buffer[0, lit_columns.min() + 2].any()


def test_sunset_processing_copy_fits_readable_ticker_area_without_shrinking_height() -> None:
    import numpy as np

    from artifact.graphics.text_utils import render_idle_style_ticker_text

    theme = THEMES["sunset-palms"]
    for text in ("ЖДИ", "НЕ УХОДИ", "СПЕРЕДИ", "СЗАДИ", "ФОТО", "НА ЧЕКЕ", "QR"):
        buffer = np.zeros((8, 48, 3), dtype=np.uint8)
        render_idle_style_ticker_text(
            buffer,
            text,
            theme.ticker_color or theme.theme_chrome,
            0.0,
            compact_static=theme.ticker_compact_static,
            safe_left=theme.ticker_safe_left,
        )
        lit_columns = np.flatnonzero(buffer.any(axis=(0, 2)))
        lit_rows = np.flatnonzero(buffer.any(axis=(1, 2)))
        assert lit_columns.min() >= theme.ticker_safe_left, text
        assert lit_columns.max() < 48, text
        assert lit_rows.min() == 0, text
        assert lit_rows.max() == 6, text


def test_sunset_ticker_hard_cuts_between_three_complete_static_labels() -> None:
    import numpy as np

    from artifact.graphics.text_utils import render_idle_style_ticker_text

    theme = THEMES["sunset-palms"]
    assert theme.ticker_idle_text_at(0) == "SUNSET"
    assert theme.ticker_idle_text_at(2199) == "SUNSET"
    assert theme.ticker_idle_text_at(2200) == "PALMS"
    assert theme.ticker_idle_text_at(4400) == "ФОТОБУДКА"
    assert theme.ticker_idle_text_at(6600) == "SUNSET"

    first = np.zeros((8, 48, 3), dtype=np.uint8)
    later = np.zeros_like(first)
    render_idle_style_ticker_text(
        first, "ФОТОБУДКА", theme.ticker_color, 0.0, compact_static=True
    )
    render_idle_style_ticker_text(
        later, "ФОТОБУДКА", theme.ticker_color, 1900.0, compact_static=True
    )

    lit_columns = np.flatnonzero(first.any(axis=(0, 2)))
    assert lit_columns.min() >= 0
    assert lit_columns.max() < 48
    assert np.array_equal(first, later)


def test_sunset_palms_prompt_is_2d_likeness_locked_and_always_receives_emblem(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)
    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_SUNSET_PALMS,
            extra_reference_images=[(PNG_1X1, "image/png")],
            prompt_variation_index=0,
        )
    )

    call = fake_client.calls[0]
    prompt = call["prompt"].lower()
    assert call["aspect_ratio"] == "9:16"
    assert call["extra_reference_images"] == [(PNG_1X1, "image/png")]
    assert "fixed underdrawing" in prompt
    assert "include each person exactly once" in prompt
    assert "inter-eye distance" in prompt
    assert "high-fidelity 2d rotoscope" in prompt
    assert "do not homogenize" in prompt
    assert "precise facial linework" in prompt
    assert "at least 70% of the background is light or mid-tone" in prompt
    assert "no black/purple night field" in prompt
    assert "ordered left-to-right" in prompt
    assert "they are not extra people" in prompt
    assert "model-native flat 2d illustrated lockup" in prompt
    assert "sunsξt geometry" in prompt
    assert "canonical emblem wording sunset palms is the only readable text" in prompt
    assert "central ding and eight distinct tone fields" in prompt
    assert "not a calm wellness retreat" in prompt
    assert "generic neon-strobe club" in prompt
    assert "dark mad max desert" in prompt
    assert "no empty bar" in prompt
    assert "canonical supplied sunset palms emblem faithfully model-rendered" in call["style"].lower()
    assert "no 3d" in call["style"].lower()
    assert "blender/octane" not in prompt
    assert "physical 3d plaque" not in prompt


def test_sunset_palms_footer_is_compact_and_emblem_is_never_overlaid() -> None:
    source = Image.new("RGB", (768, 1365), (214, 112, 94))
    for y in range(source.height):
        source.putpixel((0, y), (214, y % 255, 94))
        source.putpixel((source.width - 1, y), (214, y % 255, 94))
    buf = io.BytesIO()
    source.save(buf, format="PNG")

    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["sunset-palms"]
    result = Image.open(
        io.BytesIO(mode._stamp_sunset_palms_footer(buf.getvalue(), "ПЯТНИЦА", "22:30"))
    ).convert("RGB")

    assert result.size == source.size
    assert result.getpixel((0, result.height - 1)) == source.getpixel((0, source.height - 1))
    assert result.getpixel((result.width - 1, result.height - 1)) == source.getpixel(
        (source.width - 1, source.height - 1)
    )
    assert result.getpixel((result.width // 2, 70)) == source.getpixel((source.width // 2, 70))
    assert result.getpixel((result.width // 2, result.height - 90)) != source.getpixel(
        (source.width // 2, source.height - 90)
    )

    generation_source = inspect.getsource(PhotoboothMode._generate_photobooth_grid)
    assert "_stamp_sunset_palms_logo" not in generation_source
    assert "_stamp_sunset_palms_footer" in generation_source


def test_activation_preflight_runs_before_env_mutation_and_asset_is_valid() -> None:
    script = (ROOT / "scripts" / "activate-sunset-palms-photobooth.sh").read_text()
    check_offset = script.index('prepare-sunset-palms-idle-video.sh" --check')
    first_env_write = script.index("set_env PHOTOBOOTH_THEME sunset-palms")
    assert check_offset < first_env_write
    idle_video = ROOT / "assets/idle/sunset_palms/video/sunset-palms-fans.mp4"
    assert idle_video.exists()
    subprocess.run(
        [str(ROOT / "scripts/prepare-sunset-palms-idle-video.sh"), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_autopull_never_reactivates_an_expired_theme_by_default() -> None:
    script = (ROOT / "scripts" / "autopull.sh").read_text()
    assert 'AUTO_ACTIVATE_SUNSET_PALMS="${ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS:-0}"' in script
    assert 'AUTO_ACTIVATE_JARA="${ARTIFACT_AUTO_ACTIVATE_JARA:-0}"' in script
    assert "env_has_sunset_palms()" in script
    assert (
        'ARTIFACT_REMOTE_DIR="$REPO_DIR" '
        '"$REPO_DIR/scripts/activate-sunset-palms-photobooth.sh"'
    ) in script
    event_activation = script.split("ensure_event_activation()", 1)[1].split(
        "# Check for updates", 1
    )[0]
    assert event_activation.index("ensure_sunset_palms_activation") < event_activation.index(
        "ensure_jara_activation"
    )
