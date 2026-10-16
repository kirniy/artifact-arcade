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
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "mean_girls")
    monkeypatch.setenv("PHOTOBOOTH_THEME", "mean-girls")
    monkeypatch.setenv("ARTIFACT_CLUB_THEME_SCHEDULE", "off")
    assert [mode.theme_id_override for mode in get_configured_photobooth_modes()] == ["mean-girls"]
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES["mean-girls"]
    mode.ai_style_key_override = None
    assert mode._get_caricature_styles() == (CaricatureStyle.PHOTOBOOTH_MEAN_GIRLS_SQUARE,
                                           CaricatureStyle.PHOTOBOOTH_MEAN_GIRLS)
    mode._load_logo()
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest() == mode._theme.required_reference_sha256
    assert len(mode._theme_reference_images) == 1
    for (raw, mime), filename in zip(mode._theme_reference_images, mode._theme.reference_image_filenames):
        assert hashlib.sha256(raw).hexdigest() == mode._theme.reference_sha256_by_filename[filename]
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = mode._theme
    idle.idle_variant = idle._detect_idle_variant()
    assert idle.idle_variant == "mean_girls"
    assert idle._build_idle_scene_playlist() == [IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO] == "MEAN GIRLS"


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
    style = CaricatureStyle.PHOTOBOOTH_MEAN_GIRLS_SQUARE if square else CaricatureStyle.PHOTOBOOTH_MEAN_GIRLS
    refs = [(b"emblem", "image/png"), (b"face", "image/jpeg")]
    result = asyncio.run(service.generate_caricature(b"guests", style=style, extra_reference_images=refs))
    assert result and result.width == 90 and result.height == 160
    assert client.call["reference_photo"] == b"guests"
    assert client.call["extra_reference_images"] == refs
    assert client.call["aspect_ratio"] == ("1:1" if square else "9:16")
    assert asyncio.run(service.generate_caricature(b"guests", style=style)) is None


def test_video_full_decode_and_small_loop_reuses_frames():
    import cv2
    video = ROOT / "assets/idle/mean_girls/video/mean-girls-fans.mp4"
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
    assert len(probe["streams"]) == 1
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["codec_name"], stream["avg_frame_rate"]) == (128, 128, "h264", "24000/1001")
    assert float(probe["format"]["duration"]) == 15.056708
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], check=True)
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle.idle_variant = "mean_girls"
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
        idle.state.time = 15056.708333333334
        idle._render_cringe_circle_video(buffer)
        assert np.array_equal(first, buffer)
    finally:
        idle.cringe_circle_video_capture.release()


def test_mean_girls_footer_and_thermal_receipt_are_readable_and_qr_decodes():
    from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
    import cv2
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['mean-girls']
    buf = io.BytesIO()
    Image.new('RGB', (768, 1376), (180, 209, 205)).save(buf, format='PNG')
    stamped = mode._stamp_white_theme_footer(buf.getvalue(), 'ПЯТНИЦА', '23:05')
    image = Image.open(io.BytesIO(stamped))
    assert image.getpixel((0, 0)) == (180, 209, 205)
    footer = np.array(image)[1200:]
    assert np.count_nonzero(footer.min(axis=2) < 100) > 100
    receipt = PhotoboothRollReceiptGenerator().generate_receipt('photobooth', {
        'caricature': stamped, 'theme_id': 'mean_girls', 'timestamp': '2026-10-09T23:05:00+03:00'})
    preview = Image.open(io.BytesIO(receipt.preview_image))
    assert preview.width == 576 and preview.mode == 'L'
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(preview))
    assert decoded == 'https://vnvnc.ru/gallery/photobooth'
    assert receipt.raw_commands


def test_offline_real_guest_path_has_emblem_fonts_and_preserves_entire_photo():
    from fontTools.ttLib import TTFont
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['mean-girls']
    source = Image.new('RGB', (680, 510), (10, 20, 30))
    source.putpixel((0, 0), (255, 0, 0))
    source.putpixel((679, 509), (0, 255, 0))
    out = io.BytesIO(); source.save(out, format='PNG')
    mode._state = SimpleNamespace(photo_bytes=out.getvalue())
    display, label = asyncio.run(mode._generate_local_guest_portrait())
    image = Image.open(io.BytesIO(label))
    assert image.size == (720, 1022)
    assert image.getpixel((20, 320)) == (255, 0, 0)
    assert image.getpixel((699, 829)) == (0, 255, 0)
    assert np.asarray(image)[:310].min() < 100  # exact emblem is present
    assert Image.open(io.BytesIO(display)).size == (720, 720)
    cmap=TTFont(ROOT/'assets/fonts/mean-girls/Unbounded.ttf').getBestCmap()
    assert all(ord(c) in cmap for c in 'ПЯТНИЦА КОНЮШЕННАЯ 2В')


@pytest.mark.parametrize("entry_flag", [None, "true", "false"])
def test_activation_preserves_runtime_and_quest_entry_disables_only_print(tmp_path, entry_flag):
    import os
    import sys
    env = tmp_path / '.env'
    original = 'PHOTOBOOTH_AI_ENABLED=false\nPHOTOBOOTH_LOCAL_PORTRAIT_ENABLED=true\nGEMINI_MODEL=existing-model\nPHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=false\nARTIFACT_QUEST_PROFILE=party_exam\n'
    if entry_flag is not None:
        original += f'ARTIFACT_SPIDERVERSE_QUEST_ENABLED={entry_flag}\n'
    env.write_text(original); env.chmod(0o600)
    variables=dict(os.environ, VNVNC_PYTHON=sys.executable, ARTIFACT_ENV_FILE=str(env))
    subprocess.run(['bash', str(ROOT/'scripts/activate-mean-girls-photobooth.sh')], env=variables, check=True)
    text=env.read_text()
    for line in original.splitlines(): assert line in text
    assert 'PHOTOBOOTH_THEME=mean-girls' in text
    assert 'PHOTOBOOTH_MENU_MODES=mean_girls' in text
    if entry_flag is None:
        assert 'ARTIFACT_SPIDERVERSE_QUEST_ENABLED=' not in text
    else:
        assert f'ARTIFACT_SPIDERVERSE_QUEST_ENABLED={entry_flag}' in text
    assert 'ARTIFACT_LEGACY_QUEST_PRINT_ENABLED=false' in text
    backups=list(tmp_path.glob('.env.before-mean-girls-*'))
    assert len(backups)==1 and backups[0].read_text()==original
    assert backups[0].stat().st_mode & 0o777 == 0o600
    subprocess.run(['bash', str(ROOT/'scripts/activate-mean-girls-photobooth.sh')], env=variables, check=True)
    assert len(list(tmp_path.glob('.env.before-mean-girls-*')))==1
    assert env.read_text()==text


def test_retired_quest_does_not_append_but_normal_photo_qr_survives(monkeypatch):
    from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
    import cv2
    monkeypatch.setenv('ARTIFACT_LEGACY_QUEST_PRINT_ENABLED', 'false')
    raw=io.BytesIO();Image.new('RGB',(720,1022),'white').save(raw,format='PNG')
    data={'caricature':raw.getvalue(),'timestamp':'2026-10-17T01:00:00+03:00'}
    renderer=PhotoboothRollReceiptGenerator()
    normal=renderer.generate_receipt('photobooth',data)
    stale=renderer.generate_receipt('photobooth',dict(data,quest_start_url='https://t.me/vnvncbattlebot?start=spiderquest'))
    assert normal.preview_image==stale.preview_image
    decoded,_,_=cv2.QRCodeDetector().detectAndDecode(np.asarray(Image.open(io.BytesIO(stale.preview_image))))
    assert decoded=='https://vnvnc.ru/gallery/photobooth'
    with pytest.raises(ValueError,match='disabled'):
        renderer.generate_receipt('photobooth',dict(data,party_exam=True))


def test_mean_girls_ticker_has_short_static_labels():
    from artifact.graphics.fonts import load_font
    font=load_font('cyrillic')
    theme=THEMES['mean-girls']
    assert theme.theme_chrome==(245,5,246)
    assert all(font.measure_text(label)[0]<=48 for label in theme.ticker_idle_cycle)
    assert theme.ticker_idle_text_at(0)=='MEAN'
    assert theme.ticker_idle_text_at(2200)=='GIRLS'
    assert theme.ticker_idle_text_at(4400)=='ФОТО'
