"""Offline guest photographs: CPU foreground extraction and a light 9:16 mount."""
from __future__ import annotations

import hashlib
import io
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[3]
MODEL_SHA256 = "2355474400c5e219eb9d19f4f2f34923a2421bd61141adc446cddb6db8cc43ce"
_lock = threading.Lock()
_net = None
logger = logging.getLogger(__name__)


def foreground_mask(photo: Image.Image) -> Image.Image:
    """Use the bundled portrait-matting model; never download anything during a session."""
    import cv2
    global _net
    with _lock:
        if _net is None:
            path = ROOT / "assets/models/modnet-portrait.onnx"
            if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
                raise RuntimeError("Foreground model integrity check failed")
            _net = cv2.dnn.readNetFromONNX(str(path))
            _net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            _net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            # Oversubscribed OpenCV workers make a tiny CPU model much slower.
            if cv2.getNumThreads() > 4:
                cv2.setNumThreads(2)
        # Neutral luminance input prevents blue/magenta club light from changing
        # the segmentation class. Only the mask is inferred, never facial pixels.
        neutral = ImageOps.autocontrast(ImageOps.grayscale(photo)).convert("RGB")
        pixels = np.asarray(neutral.resize((512, 384)), dtype=np.float32) / 127.5 - 1.0
        _net.setInput(pixels.transpose(2, 0, 1)[None])
        mask = _net.forward()[0, 0]
    # Keep actual predicted silhouettes only. Never paint face circles or torso
    # polygons: Haar false positives on club lights created geometric cutouts.
    binary = (mask > .5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        raise RuntimeError("No person silhouette detected")
    largest = int(stats[1:, cv2.CC_STAT_AREA].max())
    if largest < binary.size * .01:
        raise RuntimeError("Person silhouette is too small to trust")
    keep = np.zeros(binary.shape, np.uint8)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= largest * .2:
            keep[labels == label] = 255
    keep = cv2.GaussianBlur(keep, (3, 3), .55)
    return Image.fromarray(keep).resize(photo.size, Image.Resampling.LANCZOS)



def render_guest_portrait(photo_bytes: bytes, *, theme_id: str = "twilight") -> bytes:
    """Keep real faces/poses intact; replace their surroundings with white paper."""
    photo = ImageOps.exif_transpose(Image.open(io.BytesIO(photo_bytes))).convert("RGB")
    photo.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    try:
        alpha = foreground_mask(photo)
    except Exception:
        # A segmentation failure must never lose a guest's photograph.
        logger.exception("Background removal failed; preserving the full guest photograph")
        alpha = Image.new("L", photo.size, 255)
    subject = photo.convert("RGBA")
    subject.putalpha(alpha)
    bbox = alpha.point(lambda p: 255 if p > 90 else 0).getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        pad = max(8, photo.width // 50)
        subject = subject.crop((max(0, x0-pad), max(0, y0-pad), min(photo.width, x1+pad), min(photo.height, y1+pad)))

    # A neutral photographic print avoids the saturated blue/magenta lighting
    # becoming a dark mass on thermal paper. Geometry and expressions stay real.
    gray = ImageOps.autocontrast(ImageOps.grayscale(subject.convert("RGB")), cutoff=.5)
    gray = gray.point([round(255 * (x / 255) ** .58) for x in range(256)])
    subject = Image.merge("RGBA", (gray, gray, gray, subject.getchannel("A")))
    canvas = Image.new("RGB", (720, 1280), "white")
    draw = ImageDraw.Draw(canvas)
    # Pearl/silver photographic frame with narrow beveled rails.
    for inset, color in enumerate([(58, 79, 73), (125, 143, 135), (220, 227, 223),
                                   (250, 252, 250), (233, 237, 234), (205, 216, 210),
                                   (169, 188, 179), (231, 238, 234)], start=12):
        draw.rectangle((inset, inset, 719-inset, 1110-inset+12), outline=color, width=1)
    if theme_id == "twilight":
        emblem = Image.open(ROOT / "assets/images/twilight-emblem.png").convert("RGB")
        emblem.thumbnail((250, 90), Image.Resampling.LANCZOS)
        canvas.paste(emblem, ((720-emblem.width)//2, 26))
    # Crop only empty extracted background. Large guests and a compact mount.
    window = Image.new("RGB", (664, 944), "white")
    scale = min(656 / subject.width, 936 / subject.height)
    subject = subject.resize((max(1, round(subject.width * scale)), max(1, round(subject.height * scale))), Image.Resampling.LANCZOS)
    window.paste(subject, ((664-subject.width)//2, (944-subject.height)//2), subject)
    canvas.paste(window, (28, 138))
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
