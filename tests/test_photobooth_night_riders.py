import asyncio
import hashlib
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES

ROOT = Path(__file__).resolve().parents[1]


def test_theme_menu_emblem_and_idle_wiring(monkeypatch):
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "night-riders")
    monkeypatch.setenv("PHOTOBOOTH_THEME", "night-riders")
    monkeypatch.setenv("ARTIFACT_CLUB_THEME_SCHEDULE", "off")
    assert [mode.theme_id_override for mode in get_configured_photobooth_modes()] == ["night-riders"]
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["night-riders"]
    mode.ai_style_key_override = None
    assert mode._get_caricature_styles() == (CaricatureStyle.PHOTOBOOTH_NIGHT_RIDERS_SQUARE,
                                           CaricatureStyle.PHOTOBOOTH_NIGHT_RIDERS)
    mode._load_logo()
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == mode._theme.required_reference_sha256
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = mode._theme
    idle.idle_variant = idle._detect_idle_variant()
    assert idle.idle_variant == "night_riders"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "NIGHT RIDERS"


@pytest.mark.parametrize("square", [False, True])
def test_generation_keeps_identity_references_and_requested_format(square):
    output = io.BytesIO()
    Image.new("RGB", (90, 160), "white").save(output, format="PNG")
    class Client:
        is_available = True
        async def generate_image(self, **kwargs):
            self.call = kwargs
            return output.getvalue()
    client = Client()
    service = CaricatureService.__new__(CaricatureService)
    service._client = client
    style = CaricatureStyle.PHOTOBOOTH_NIGHT_RIDERS_SQUARE if square else CaricatureStyle.PHOTOBOOTH_NIGHT_RIDERS
    refs = [(b"emblem", "image/png"), (b"face", "image/jpeg")]
    result = asyncio.run(service.generate_caricature(b"guests", style=style, extra_reference_images=refs))
    assert result and result.width == 90 and result.height == 160
    assert client.call["reference_photo"] == b"guests"
    assert client.call["extra_reference_images"] == refs
    assert client.call["aspect_ratio"] == ("1:1" if square else "9:16")
    assert asyncio.run(service.generate_caricature(b"guests", style=style)) is None


def test_video_full_decode_and_small_loop_reuses_frames():
    import cv2
    video = ROOT / "assets/idle/night_riders/video/night-riders-fans.mp4"
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    assert len(probe["streams"]) == 1
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["codec_name"], stream["avg_frame_rate"]) == (128, 128, "h264", "24/1")
    assert float(probe["format"]["duration"]) == 120
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], check=True)
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle.idle_variant = "night_riders"
    idle._cv2_available = True
    idle.cringe_circle_video_capture = cv2.VideoCapture(str(video))
    idle.state = SimpleNamespace(time=0)
    idle._tropical_video_start_ms = 0
    idle._tropical_video_frame_index = -1
    idle._tropical_video_frame = None
    idle._draw_cringe_overlay = lambda *args: None
    buffer = np.zeros((128, 128, 3), dtype=np.uint8)
    try:
        idle._render_cringe_circle_video(buffer)
        first = buffer.copy()
        idle.state.time = 16
        idle._render_cringe_circle_video(buffer)
        assert np.array_equal(first, buffer)
        idle.state.time = 120000
        idle._render_cringe_circle_video(buffer)
        assert np.array_equal(first, buffer)
    finally:
        idle.cringe_circle_video_capture.release()


def test_night_receipt_lifts_background_and_preserves_footer_without_mutating_source(monkeypatch):
    from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
    from PIL import ImageDraw
    image = Image.new('RGB', (544, 900), (8, 12, 20))
    draw = ImageDraw.Draw(image)
    draw.ellipse((150, 180, 370, 400), fill=(190, 150, 130))
    draw.rectangle((0, 783, 543, 899), fill='white')
    draw.text((20, 810), 'VNVNC.RU', fill='black')
    before = image.tobytes()
    generator = PhotoboothRollReceiptGenerator()
    lifted = generator._prepare_night_riders_photo(image)
    assert lifted.getpixel((50, 50)) >= 170
    assert lifted.crop((0, 783, 544, 900)).tobytes() == image.convert('L').crop((0, 783, 544, 900)).tobytes()
    assert image.tobytes() == before
    # Other themes must retain their existing unmodified image path.
    calls = []
    original = generator._prepare_night_riders_photo
    generator._prepare_night_riders_photo = lambda photo: (calls.append(True) or original(photo))
    monkeypatch.setenv('PHOTOBOOTH_PRINT_FORTUNES', 'false')
    generator.generate_receipt('photobooth', {'caricature': image, 'theme_id': 'bannaya'})
    assert not calls
    receipt = generator.generate_receipt('photobooth', {'caricature': image, 'theme_id': 'night-riders'})
    assert calls and receipt.raw_commands and receipt.preview_image
