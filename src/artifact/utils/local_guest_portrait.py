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
MODEL_SHA256 = "552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24"
_lock = threading.Lock()
_net = None
logger = logging.getLogger(__name__)


def foreground_mask(photo: Image.Image) -> Image.Image:
    """Use the bundled PPHumanSeg model; never download anything during a session."""
    import cv2
    global _net
    with _lock:
        if _net is None:
            path = ROOT / "assets/models/pphumanseg.onnx"
            if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
                raise RuntimeError("Foreground model integrity check failed")
            _net = cv2.dnn.readNetFromONNX(str(path))
            _net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            _net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            # Oversubscribed OpenCV workers make a tiny CPU model much slower.
            if cv2.getNumThreads() > 4:
                cv2.setNumThreads(2)
        pixels = np.asarray(photo.resize((192, 192)), dtype=np.float32) / 127.5 - 1.0
        _net.setInput(pixels.transpose(2, 0, 1)[None])
        mask = _net.forward()[0, 1]
        # Club color washes can hide a person from the RGB detector. A second
        # luminance pass recovers those bodies; the original photo stays untouched.
        gray_pixels = np.asarray(ImageOps.grayscale(photo).convert("RGB").resize((192, 192)), dtype=np.float32) / 127.5 - 1.0
        _net.setInput(gray_pixels.transpose(2, 0, 1)[None])
        mask = np.maximum(mask, _net.forward()[0, 1])
    lo, hi = float(mask.min()), float(mask.max())
    if hi - lo < 1e-5:
        raise RuntimeError("Foreground detector returned an empty mask")
    mask = np.clip((mask - lo) / (hi - lo), 0, 1)
    # Keep solid people rather than washing faces out with an uncertain soft mask.
    mask = cv2.dilate((mask > .35).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    mask = cv2.GaussianBlur(mask, (3, 3), .6)
    alpha = Image.fromarray(mask).resize(photo.size, Image.Resampling.LANCZOS)
    # Protect detected facial pixels even under saturated magenta club lighting.
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gray = cv2.equalizeHist(cv2.cvtColor(np.asarray(photo), cv2.COLOR_RGB2GRAY))
    faces = detector.detectMultiScale(gray, 1.05, 2, minSize=(15, 15))
    draw = ImageDraw.Draw(alpha)
    for x, y, w, h in faces:
        draw.ellipse((int(x-w*.12), int(y-h*.15), int(x+w*1.12), int(y+h*1.15)), fill=255)
        # Clipped/flashed shirts are often classified as background. Preserve
        # the torso beneath each visible face so nobody becomes a floating head.
        center = x + w / 2
        bottom = min(photo.height, y + h * 4.5)
        draw.polygon([(int(center-w*.55), int(y+h*.8)),
                      (int(center+w*.55), int(y+h*.8)),
                      (int(center+w*1.35), int(bottom)),
                      (int(center-w*1.35), int(bottom))], fill=255)
    return alpha


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

    canvas = Image.new("RGB", (720, 1280), (249, 250, 247))
    draw = ImageDraw.Draw(canvas)
    green, silver = (47, 76, 66), (166, 184, 174)
    # Fine double rails and four engraved botanical corners, mostly white for paper.
    draw.rectangle((14, 14, 705, 1110), outline=green, width=3)
    draw.rectangle((23, 23, 696, 1101), outline=silver, width=1)
    for x, dx in ((32, 1), (687, -1)):
        for y, dy in ((34, 1), (1090, -1)):
            draw.line((x, y, x+dx*66, y), fill=green, width=2)
            draw.line((x, y, x, y+dy*66), fill=green, width=2)
            for offset in (16, 32, 48):
                draw.ellipse((min(x+dx*4, x+dx*13), min(y+dy*offset, y+dy*(offset+19)), max(x+dx*4, x+dx*13), max(y+dy*offset, y+dy*(offset+19))), outline=silver, width=2)
    if theme_id == "twilight":
        emblem = Image.open(ROOT / "assets/images/twilight-emblem.png").convert("RGB")
        # The canonical white-backed original is kept intact, never redrawn.
        emblem.thumbnail((300, 110), Image.Resampling.LANCZOS)
        canvas.paste(emblem, ((720-emblem.width)//2, 45))
    draw.line((100, 174, 620, 174), fill=silver, width=1)
    # A generous photo window, with no crop that could cut out another guest.
    window = Image.new("RGB", (640, 850), "white")
    scale = min(620 / subject.width, 830 / subject.height)
    subject = subject.resize((round(subject.width * scale), round(subject.height * scale)), Image.Resampling.LANCZOS)
    window.paste(subject, ((640-subject.width)//2, (850-subject.height)//2), subject)
    canvas.paste(window, (40, 200))
    draw.rectangle((38, 198, 681, 1051), outline=silver, width=2)
    draw.line((170, 1080, 550, 1080), fill=silver, width=1)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
