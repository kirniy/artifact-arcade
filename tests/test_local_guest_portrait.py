import asyncio
import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from artifact.utils.local_guest_portrait import render_guest_portrait
from artifact.modes.photobooth import PhotoboothMode
from artifact.modes.photobooth_themes import THEMES


def test_complete_frame_is_preserved_without_inference(monkeypatch):
    import socket
    # Offline processing must not even attempt a model or network call.
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    photo = Image.new('RGB', (680, 510), (184, 51, 27))
    photo.putpixel((0, 0), (255, 0, 0))
    photo.putpixel((679, 509), (0, 255, 0))
    raw = io.BytesIO(); photo.save(raw, format='PNG')
    original = raw.getvalue()
    result = Image.open(io.BytesIO(render_guest_portrait(original)))
    assert result.size == (720, 930)
    assert result.getpixel((20, 228)) == (255, 0, 0)
    assert result.getpixel((699, 737)) == (0, 255, 0)
    pixel = result.getpixel((360, 500))
    assert pixel[0] > pixel[1] > pixel[2]  # Colour survives digital sharing.
    assert raw.getvalue() == original
    assert result.getpixel((0, 0)) == (255, 255, 255)


def test_local_mode_returns_print_and_display_without_ai(monkeypatch):
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['twilight']
    raw = io.BytesIO(); Image.new('RGB', (100, 100), 'red').save(raw, format='PNG')
    mode._state = SimpleNamespace(photo_bytes=raw.getvalue())
    display, label = asyncio.run(mode._generate_local_guest_portrait())
    assert Image.open(io.BytesIO(label)).size == (720, 1100)
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


def test_tall_photo_is_bounded_and_footer_never_overwrites_photograph():
    raw = io.BytesIO(); Image.new('RGB', (20, 1000), 'red').save(raw, format='PNG')
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._theme = THEMES['twilight']
    output = render_guest_portrait(raw.getvalue())
    image = Image.open(io.BytesIO(output))
    assert image.size == (720, 1380)
    stamped = Image.open(io.BytesIO(mode._stamp_white_theme_footer(output, 'ПЯТНИЦА', '23:41')))
    assert stamped.getpixel((360, 1187)) == (255, 0, 0)
