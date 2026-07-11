import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from artifact.modes.photobooth import PhotoboothMode, PhotoboothState


class _FakeDetector:
    def __init__(self, name: str, calls: list[tuple[str, int]]) -> None:
        self.name = name
        self.calls = calls

    def empty(self) -> bool:
        return False

    def detectMultiScale(self, image, *, minNeighbors, **_kwargs):
        self.calls.append((self.name, minNeighbors))
        if self.name == "haarcascade_frontalface_default.xml" and minNeighbors == 3:
            return np.array([[10, 10, 30, 30]])
        return np.empty((0, 4), dtype=np.int32)


class PhotoboothFaceGateTests(unittest.TestCase):
    def _photo_bytes(self) -> bytes:
        output = io.BytesIO()
        Image.new("RGB", (64, 64), "black").save(output, format="JPEG")
        return output.getvalue()

    def test_permissive_fallback_recovers_strict_face_miss(self) -> None:
        calls: list[tuple[str, int]] = []
        with tempfile.TemporaryDirectory() as directory:
            for name in (
                "haarcascade_frontalface_default.xml",
                "haarcascade_frontalface_alt2.xml",
                "haarcascade_profileface.xml",
            ):
                Path(directory, name).touch()

            fake_cv2 = types.SimpleNamespace(
                data=types.SimpleNamespace(haarcascades=directory),
                COLOR_RGB2GRAY=1,
                CASCADE_SCALE_IMAGE=2,
                cvtColor=lambda frame, _code: np.zeros(frame.shape[:2], dtype=np.uint8),
                equalizeHist=lambda image: image,
                flip=lambda image, _axis: image,
                CascadeClassifier=lambda path: _FakeDetector(Path(path).name, calls),
            )
            mode = object.__new__(PhotoboothMode)
            mode._state = PhotoboothState(photo_bytes=self._photo_bytes())

            with patch.dict(sys.modules, {"cv2": fake_cv2}):
                self.assertTrue(mode._source_photo_has_visible_face())

        self.assertEqual(calls[:2], [
            ("haarcascade_frontalface_default.xml", 4),
            ("haarcascade_frontalface_default.xml", 3),
        ])

    def test_missing_detectors_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_cv2 = types.SimpleNamespace(
                data=types.SimpleNamespace(haarcascades=directory),
                COLOR_RGB2GRAY=1,
                CASCADE_SCALE_IMAGE=2,
                cvtColor=lambda frame, _code: np.zeros(frame.shape[:2], dtype=np.uint8),
                equalizeHist=lambda image: image,
                flip=lambda image, _axis: image,
            )
            mode = object.__new__(PhotoboothMode)
            mode._state = PhotoboothState(photo_bytes=self._photo_bytes())

            with patch.dict(sys.modules, {"cv2": fake_cv2}):
                self.assertTrue(mode._source_photo_has_visible_face())


if __name__ == "__main__":
    unittest.main()
