import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.ai.caricature import CaricatureService, CaricatureStyle


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9kAAAAASUVORK5CYII="
)


class FakeGeminiClient:
    def __init__(self) -> None:
        self.is_available = True
        self.calls = []

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return PNG_1X1


def test_vnvnc_bday_label_style_requests_vertical_9_16(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)

    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY,
            personality_context="TEST WEEKDAY TEST TIME",
        )
    )

    assert fake_client.calls[0]["aspect_ratio"] == "9:16"


def test_vnvnc_bday_display_style_requests_square_1_1(monkeypatch) -> None:
    fake_client = FakeGeminiClient()
    monkeypatch.setattr("artifact.ai.caricature.get_gemini_client", lambda: fake_client)

    service = CaricatureService()
    asyncio.run(
        service.generate_caricature(
            reference_photo=b"fake-jpeg",
            style=CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY_SQUARE,
            personality_context="TEST WEEKDAY TEST TIME",
        )
    )

    assert fake_client.calls[0]["aspect_ratio"] == "1:1"
