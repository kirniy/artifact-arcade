import asyncio
import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from artifact.utils.local_guest_portrait import foreground_mask, render_guest_portrait
from artifact.modes.photobooth import PhotoboothMode
from artifact.modes.photobooth_themes import THEMES


def test_real_model_loads_on_cpu_and_framed_portrait_has_exact_ratio():
    photo = Image.new('RGB', (400, 300), (120, 70, 80))
    import cv2
    from artifact.utils.local_guest_portrait import ROOT
    net = cv2.dnn.readNetFromONNX(str(ROOT / 'assets/models/modnet-portrait.onnx'))
    net.setInput(np.zeros((1, 3, 384, 512), dtype=np.float32))
    assert net.forward().shape == (1, 1, 384, 512)
    raw = io.BytesIO()
    photo.save(raw, format='JPEG')
    result = Image.open(io.BytesIO(render_guest_portrait(raw.getvalue())))
    assert result.size == (720, 1280)
    assert result.getpixel((45, 205)) == (255, 255, 255)


def test_compositor_preserves_foreground_pixels_and_original_bytes(monkeypatch):
    import artifact.utils.local_guest_portrait as module
    photo = Image.new('RGB', (100, 100), (184, 51, 27))
    raw = io.BytesIO(); photo.save(raw, format='PNG')
    original = raw.getvalue()
    monkeypatch.setattr(module, 'foreground_mask', lambda p: Image.new('L', p.size, 255))
    result = Image.open(io.BytesIO(render_guest_portrait(original)))
    pixel = result.getpixel((360, 625))
    assert pixel[0] == pixel[1] == pixel[2] and pixel[0] > 0
    assert raw.getvalue() == original


def test_local_mode_returns_print_and_display_without_ai(monkeypatch):
    import artifact.utils.local_guest_portrait as module
    monkeypatch.setattr(module, 'foreground_mask', lambda p: Image.new('L', p.size, 255))
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['twilight']
    raw = io.BytesIO(); Image.new('RGB', (100, 100), 'red').save(raw, format='PNG')
    mode._state = SimpleNamespace(photo_bytes=raw.getvalue())
    display, label = asyncio.run(mode._generate_local_guest_portrait())
    assert Image.open(io.BytesIO(label)).size == (720, 1280)
    assert Image.open(io.BytesIO(display)).size == (720, 720)
    assert mode._state.photo_bytes == raw.getvalue()


def test_capture_routes_directly_to_local_task_without_cloud(monkeypatch):
    monkeypatch.setenv('PHOTOBOOTH_LOCAL_PORTRAIT_ENABLED', 'true')
    async def check():
        mode = PhotoboothMode.__new__(PhotoboothMode)
        mode._ai_enabled = False
        mode._state = SimpleNamespace()
        mode._progress_tracker = SimpleNamespace(start=lambda: None)
        raw = io.BytesIO(); Image.new('RGB', (100, 100), 'red').save(raw, format='JPEG')
        mode._capture_selected_camera_jpeg = lambda **kw: raw.getvalue()
        mode.change_phase = lambda phase: None
        async def local():
            return b'display', b'label'
        mode._generate_local_guest_portrait = local
        mode._do_flash_and_capture()
        assert mode._state.is_generating
        assert await mode._ai_task == (b'display', b'label')
        assert mode._state.photo_bytes == raw.getvalue()
    asyncio.run(check())


def test_mask_never_paints_false_face_shapes_and_discards_detached_noise(monkeypatch):
    import cv2
    import artifact.utils.local_guest_portrait as module
    prediction = np.zeros((1, 1, 384, 512), dtype=np.float32)
    prediction[0, 0, 90:370, 140:380] = 1
    prediction[0, 0, 10:15, 10:15] = 1
    class Net:
        def setInput(self, pixels):
            assert pixels.shape == (1, 3, 384, 512)
        def forward(self):
            return prediction
    monkeypatch.setattr(module, '_net', Net())
    def forbidden(*args):
        raise AssertionError('Face detection must not create geometry in the mask')
    monkeypatch.setattr(cv2, 'CascadeClassifier', forbidden)
    mask = module.foreground_mask(Image.new('RGB', (512, 384), 'blue'))
    assert mask.getpixel((250, 200)) == 255
    assert mask.getpixel((12, 12)) == 0
    assert mask.getpixel((100, 200)) == 0
