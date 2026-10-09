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
    mask = foreground_mask(photo)
    assert mask.size == photo.size
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
    assert result.getpixel((360, 625)) == (184, 51, 27)
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
