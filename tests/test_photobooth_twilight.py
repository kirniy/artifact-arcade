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
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "twilight")
    monkeypatch.setenv("PHOTOBOOTH_THEME", "twilight")
    monkeypatch.setenv("ARTIFACT_CLUB_THEME_SCHEDULE", "off")
    assert [mode.theme_id_override for mode in get_configured_photobooth_modes()] == ["twilight"]
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["twilight"]
    mode.ai_style_key_override = None
    assert mode._get_caricature_styles() == (CaricatureStyle.PHOTOBOOTH_TWILIGHT_SQUARE,
                                           CaricatureStyle.PHOTOBOOTH_TWILIGHT)
    mode._load_logo()
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == mode._theme.required_reference_sha256
    assert len(mode._theme_reference_images) == 2
    for (raw, mime), filename in zip(mode._theme_reference_images, mode._theme.reference_image_filenames):
        assert hashlib.sha256(raw).hexdigest() == mode._theme.reference_sha256_by_filename[filename]
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = mode._theme
    idle.idle_variant = idle._detect_idle_variant()
    assert idle.idle_variant == "twilight"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "TWILIGHT"


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
    style = CaricatureStyle.PHOTOBOOTH_TWILIGHT_SQUARE if square else CaricatureStyle.PHOTOBOOTH_TWILIGHT
    refs = [(b"emblem", "image/png"), (b"forest", "image/png"), (b"face", "image/jpeg")]
    result = asyncio.run(service.generate_caricature(b"guests", style=style, extra_reference_images=refs))
    assert result and result.width == 90 and result.height == 160
    assert client.call["reference_photo"] == b"guests"
    assert client.call["extra_reference_images"] == refs
    assert client.call["aspect_ratio"] == ("1:1" if square else "9:16")
    assert asyncio.run(service.generate_caricature(b"guests", style=style)) is None


def test_video_full_decode_and_small_loop_reuses_frames():
    import cv2
    video = ROOT / "assets/idle/twilight/video/twilight-fans.mp4"
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    assert len(probe["streams"]) == 1
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["codec_name"], stream["avg_frame_rate"]) == (128, 128, "h264", "30/1")
    assert float(probe["format"]["duration"]) == 60
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], check=True)
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle.idle_variant = "twilight"
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
        idle.state.time = 60000
        idle._render_cringe_circle_video(buffer)
        assert np.array_equal(first, buffer)
    finally:
        idle.cringe_circle_video_capture.release()


def test_twilight_footer_and_thermal_receipt_are_readable_and_qr_decodes():
    from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
    import cv2
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['twilight']
    buf = io.BytesIO()
    Image.new('RGB', (768, 1376), (180, 209, 205)).save(buf, format='PNG')
    stamped = mode._stamp_white_theme_footer(buf.getvalue(), 'ПЯТНИЦА', '23:05')
    image = Image.open(io.BytesIO(stamped))
    assert image.getpixel((0, 0)) == (180, 209, 205)
    footer = np.array(image)[1200:]
    assert np.count_nonzero(footer.min(axis=2) < 100) > 100
    receipt = PhotoboothRollReceiptGenerator().generate_receipt('photobooth', {
        'caricature': stamped, 'theme_id': 'twilight', 'timestamp': '2026-10-09T23:05:00+03:00'})
    preview = Image.open(io.BytesIO(receipt.preview_image))
    assert preview.width == 576 and preview.mode == 'L'
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(preview))
    assert decoded == 'https://vnvnc.ru/gallery/photobooth'
    assert receipt.raw_commands
