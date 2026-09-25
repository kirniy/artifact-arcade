"""The new БАННАЯ flow must reach the right prompt, assets, and idle player."""

import asyncio
import hashlib
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from artifact.ai.bannaya import SCENES, build_prompt
from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES


ROOT = Path(__file__).resolve().parents[1]


def test_menu_selects_new_theme_without_replacing_old_one(monkeypatch):
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "bannaya")
    assert [mode.theme_id_override for mode in get_configured_photobooth_modes()] == ["bannaya"]
    assert THEMES["banya_chic"].event_name == "БАННЫЙ ШИК"
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["bannaya"]
    mode.ai_style_key_override = None
    assert mode._get_caricature_styles() == (
        CaricatureStyle.PHOTOBOOTH_BANNAYA_SQUARE,
        CaricatureStyle.PHOTOBOOTH_BANNAYA,
    )
    mode._load_logo()
    assert len(mode._theme_reference_images) == 1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == mode._theme.required_reference_sha256


@pytest.mark.parametrize("square", [False, True])
def test_generation_dispatch_and_missing_emblem_fail_closed(square):
    image = io.BytesIO()
    Image.new("RGB", (90, 160), "white").save(image, format="PNG")

    class Client:
        is_available = True

        async def generate_image(self, **kwargs):
            self.call = kwargs
            return image.getvalue()

    client = Client()
    service = CaricatureService.__new__(CaricatureService)
    service._client = client
    style = CaricatureStyle.PHOTOBOOTH_BANNAYA_SQUARE if square else CaricatureStyle.PHOTOBOOTH_BANNAYA
    refs = [(b"approved-emblem", "image/png"), (b"guest-face", "image/jpeg")]
    result = asyncio.run(service.generate_caricature(b"guests", style=style, extra_reference_images=refs, prompt_variation_index=2))
    assert result and result.width == 90 and result.height == 160
    assert client.call["reference_photo"] == b"guests"
    assert client.call["extra_reference_images"] == refs
    assert client.call["aspect_ratio"] == ("1:1" if square else "9:16")
    assert SCENES[2] in client.call["prompt"]
    assert asyncio.run(service.generate_caricature(b"guests", style=style)) is None


def test_idle_uses_approved_loop_and_decodes_completely():
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES["bannaya"]
    idle.idle_variant = idle._detect_idle_variant()
    assert idle.idle_variant == "bannaya"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "БАННАЯ"
    video = ROOT / "assets/idle/bannaya/video/bannaya-fans.mp4"
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    assert len(probe["streams"]) == 1
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["codec_name"], stream["avg_frame_rate"]) == (128, 128, "h264", "24/1")
    assert float(probe["format"]["duration"]) > 130
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], check=True)


def test_prompt_varies_without_dark_receipt_background():
    assert len({build_prompt(index) for index in range(4)}) == 4
    for index in range(4):
        prompt = build_prompt(index)
        assert "BLACK-AND-WHITE thermal label" in prompt
        assert "БАННЫЙ ШИК" in prompt  # Explicitly excludes the old event.
        assert "Клуб Романтики" in prompt
        assert "Dress EVERY guest" in prompt and "bathrobe" in prompt
        assert "Absolutely no photorealism" in prompt
        assert "POSE LOCK" in prompt and "ethnic features" in prompt


def test_idle_player_reuses_frame_and_wraps_to_start():
    import cv2

    video = ROOT / "assets/idle/bannaya/video/bannaya-fans.mp4"
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle.idle_variant = "bannaya"
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
        frames = int(idle.cringe_circle_video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        idle.state.time = frames * 1000 / 24
        idle._render_cringe_circle_video(buffer)
        assert np.array_equal(first, buffer)
    finally:
        idle.cringe_circle_video_capture.release()
