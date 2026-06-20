"""Standalone CRT video-wall renderer.

This process is intentionally independent from the photobooth mode. It owns the
HDMI capture card, publishes raw shared frames for the photobooth Camera 2
selector, applies a light VHS/CRT treatment, and renders to the configured
output.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _data_dir() -> Path:
    return Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass
class VideoWallConfig:
    device: str = os.environ.get("VNVNC_VIDEO_WALL_DEVICE", "/dev/video0")
    capture_width: int = int(os.environ.get("VNVNC_VIDEO_WALL_CAPTURE_WIDTH", "640"))
    capture_height: int = int(os.environ.get("VNVNC_VIDEO_WALL_CAPTURE_HEIGHT", "480"))
    capture_fps: int = int(os.environ.get("VNVNC_VIDEO_WALL_CAPTURE_FPS", "25"))
    output_width: int = int(os.environ.get("VNVNC_VIDEO_WALL_OUTPUT_WIDTH", "720"))
    output_height: int = int(os.environ.get("VNVNC_VIDEO_WALL_OUTPUT_HEIGHT", "480"))
    output: str = os.environ.get("VNVNC_VIDEO_WALL_OUTPUT", "pygame")
    display_index: int = int(os.environ.get("VNVNC_VIDEO_WALL_DISPLAY_INDEX", "1"))
    drm_card: str = os.environ.get("VNVNC_VIDEO_WALL_DRM_CARD", "/dev/dri/card1")
    drm_connector: str = os.environ.get("VNVNC_VIDEO_WALL_DRM_CONNECTOR", "HDMI-A-2")
    fbdev_path: str = os.environ.get("VNVNC_VIDEO_WALL_FBDEV", "/dev/fb0")
    capture_fourcc: str = os.environ.get("VNVNC_VIDEO_WALL_CAPTURE_FOURCC", "MJPG").strip().upper()
    logo_path: Path = Path(
        os.environ.get(
            "VNVNC_VIDEO_WALL_LOGO",
            str(_repo_root() / "assets" / "video_wall" / "flame-logo.png"),
        )
    )
    shared_frame_path: Path = Path(
        os.environ.get(
            "VNVNC_HDMI_CAPTURE_SHARED_FRAME",
            str(_data_dir() / "video_wall" / "hdmi_capture_latest.jpg"),
        )
    )
    heartbeat_path: Path = Path(
        os.environ.get("VNVNC_VIDEO_WALL_HEARTBEAT", str(_data_dir() / "video_wall" / "heartbeat"))
    )
    primary_shared_frame_path: Path = Path(
        os.environ.get(
            "VNVNC_PRIMARY_CAMERA_SHARED_FRAME",
            str(_data_dir() / "video_wall" / "primary_camera_latest.jpg"),
        )
    )
    primary_max_age: float = float(os.environ.get("VNVNC_PRIMARY_CAMERA_SHARED_MAX_AGE", "1.0"))
    switch_interval_seconds: float = float(os.environ.get("VNVNC_VIDEO_WALL_SWITCH_INTERVAL", "28"))
    primary_window_seconds: float = float(os.environ.get("VNVNC_VIDEO_WALL_PRIMARY_WINDOW", "7"))
    shared_publish_fps: float = float(os.environ.get("VNVNC_VIDEO_WALL_SHARED_PUBLISH_FPS", "6"))
    headless_frames: int = int(os.environ.get("VNVNC_VIDEO_WALL_HEADLESS_FRAMES", "90"))
    headless_output_path: Path = Path(
        os.environ.get("VNVNC_VIDEO_WALL_HEADLESS_OUTPUT", "/tmp/vnvnc-video-wall-frame.jpg")
    )
    display_year: Optional[int] = (
        int(os.environ["VNVNC_VIDEO_WALL_DISPLAY_YEAR"])
        if os.environ.get("VNVNC_VIDEO_WALL_DISPLAY_YEAR")
        else 2017
    )


class VideoWallRenderer:
    def __init__(self, config: VideoWallConfig):
        self.config = config
        self._running = True
        self._capture = None
        self._screen = None
        self._clock = None
        self._kms_crtc = None
        self._kms_plane = None
        self._kms_fb = None
        self._kms_fb_view = None
        self._kms_stride = 0
        self._pykms_frame_count = 0
        self._fbdev = None
        self._last_capture_open_attempt = 0.0
        self._logo = self._load_logo()
        self._last_shared_publish = 0.0
        self._last_frame: Optional[np.ndarray] = None

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        self.config.shared_frame_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config.output == "headless":
            self._run_headless()
            return

        self._open_capture(required=False)
        self._init_output()
        try:
            frame_interval = 1.0 / max(1, self.config.capture_fps)
            while self._running:
                start = time.time()
                raw = self._next_source_frame()
                if raw is None:
                    raw = self._placeholder_frame()
                self._publish_shared_frame(raw)
                rendered = self._render_frame(raw, time.time())
                self._show_frame(rendered)
                self._touch_heartbeat()
                elapsed = time.time() - start
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
        finally:
            self._cleanup()

    def _run_headless(self) -> None:
        logger.info("Running video wall renderer in headless test mode")
        for i in range(max(1, self.config.headless_frames)):
            raw = self._placeholder_frame(i / max(1, self.config.capture_fps))
            self._publish_shared_frame(raw, force=True)
            rendered = self._render_frame(raw, time.time())
            if i == self.config.headless_frames - 1:
                Image.fromarray(rendered).save(self.config.headless_output_path, quality=90)
            self._touch_heartbeat()
        logger.info("Headless frame written to %s", self.config.headless_output_path)

    def _open_capture(self, required: bool = True) -> bool:
        now = time.time()
        if self._capture is not None:
            return True
        if not required and now - self._last_capture_open_attempt < 2.0:
            return False
        self._last_capture_open_attempt = now

        try:
            import cv2
        except Exception as e:
            if required:
                raise RuntimeError(f"OpenCV is required for video wall capture: {e}") from e
            logger.warning("OpenCV unavailable for video wall capture: %s", e)
            return False

        capture = cv2.VideoCapture(self.config.device, cv2.CAP_V4L2)
        if not capture.isOpened():
            if required:
                raise RuntimeError(f"Failed to open HDMI capture card at {self.config.device}")
            logger.warning("Video wall HDMI capture unavailable at %s; rendering placeholder", self.config.device)
            capture.release()
            return False
        if self.config.capture_fourcc:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.config.capture_fourcc[:4]))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.capture_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.capture_height)
        capture.set(cv2.CAP_PROP_FPS, self.config.capture_fps)
        self._capture = capture
        logger.info(
            "Opened HDMI capture card %s at %sx%s@%s fourcc=%s",
            self.config.device,
            self.config.capture_width,
            self.config.capture_height,
            self.config.capture_fps,
            self.config.capture_fourcc or "default",
        )
        return True

    def _init_output(self) -> None:
        if self.config.output == "fbdev":
            self._init_fbdev_output()
            return
        if self.config.output == "pykms":
            self._init_pykms_output()
            return
        if self.config.output != "pygame":
            raise RuntimeError(f"Unsupported video wall output: {self.config.output}")

        os.environ.setdefault("SDL_VIDEO_FULLSCREEN_DISPLAY", str(self.config.display_index))
        os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "0")
        import pygame

        pygame.init()
        pygame.display.init()
        self._screen = pygame.display.set_mode(
            (self.config.output_width, self.config.output_height),
            pygame.FULLSCREEN,
        )
        pygame.mouse.set_visible(False)
        pygame.display.set_caption("VNVNC CRT VIDEO WALL")
        self._clock = pygame.time.Clock()
        logger.info(
            "Initialized pygame output %sx%s on display index %s",
            self.config.output_width,
            self.config.output_height,
            self.config.display_index,
        )

    def _init_pykms_output(self) -> None:
        try:
            import pykms
        except Exception as e:
            raise RuntimeError(f"pykms is required for DRM video wall output: {e}") from e

        card = pykms.Card(self.config.drm_card)
        connector = next((c for c in card.connectors if c.fullname == self.config.drm_connector), None)
        if connector is None:
            raise RuntimeError(f"DRM connector not found: {self.config.drm_connector}")
        if not connector.connected():
            raise RuntimeError(f"DRM connector is not connected: {self.config.drm_connector}")

        crtc = connector.get_current_crtc()
        if crtc is None:
            raise RuntimeError(f"DRM connector has no active CRTC: {self.config.drm_connector}")

        mode = next(
            (
                m
                for m in connector.get_modes()
                if int(getattr(m, "hdisplay", 0)) == self.config.output_width
                and int(getattr(m, "vdisplay", 0)) == self.config.output_height
            ),
            crtc.mode,
        )
        width = int(getattr(mode, "hdisplay", self.config.output_width))
        height = int(getattr(mode, "vdisplay", self.config.output_height))
        self.config.output_width = width
        self.config.output_height = height

        fb = pykms.DumbFramebuffer(card, width, height, pykms.PixelFormat.XRGB8888)
        current_mode = crtc.mode
        current_width = int(getattr(current_mode, "hdisplay", 0))
        current_height = int(getattr(current_mode, "vdisplay", 0))
        if (current_width, current_height) != (width, height):
            mode_result = crtc.set_mode(connector, fb, mode)
            if mode_result < 0:
                raise RuntimeError(
                    f"Failed to set DRM mode {width}x{height} on {self.config.drm_connector}: {mode_result}"
                )
        self._kms_crtc = crtc
        self._kms_plane = crtc.primary_plane
        self._kms_fb = fb
        self._kms_fb_view = fb.map(0).cast("B")
        self._kms_stride = fb.stride(0)

        logger.info(
            "Initialized pykms output %sx%s on %s (%s), crtc=%s plane=%s",
            width,
            height,
            self.config.drm_connector,
            self.config.drm_card,
            crtc.id,
            self._kms_plane.id,
        )

    def _init_fbdev_output(self) -> None:
        self._fbdev = open(self.config.fbdev_path, "r+b", buffering=0)
        logger.info(
            "Initialized fbdev output %sx%s on %s",
            self.config.output_width,
            self.config.output_height,
            self.config.fbdev_path,
        )

    def _next_source_frame(self) -> Optional[np.ndarray]:
        primary = self._read_primary_shared_frame_if_active()
        if primary is not None:
            return primary
        return self._read_capture_frame()

    def _read_capture_frame(self) -> Optional[np.ndarray]:
        if self._capture is None:
            self._open_capture(required=False)
            if self._capture is None:
                return None
        try:
            import cv2

            ok, frame_bgr = self._capture.read()
            if not ok or frame_bgr is None:
                return self._last_frame
            frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            self._last_frame = frame
            return frame
        except Exception as e:
            logger.debug("Capture read failed: %s", e)
            return self._last_frame

    def _read_primary_shared_frame_if_active(self) -> Optional[np.ndarray]:
        if self.config.switch_interval_seconds <= 0 or self.config.primary_window_seconds <= 0:
            return None
        cycle = time.time() % self.config.switch_interval_seconds
        if cycle > self.config.primary_window_seconds:
            return None
        try:
            age = time.time() - self.config.primary_shared_frame_path.stat().st_mtime
            if age > self.config.primary_max_age:
                return None
            return np.array(Image.open(self.config.primary_shared_frame_path).convert("RGB"), dtype=np.uint8)
        except OSError:
            return None
        except Exception as e:
            logger.debug("Failed to read primary shared camera frame: %s", e)
            return None

    def _render_frame(self, raw: np.ndarray, now: float) -> np.ndarray:
        frame = self._fit_to_output(raw)
        frame = self._apply_vhs(frame, now)
        frame = self._overlay_logo(frame, now)
        frame = self._overlay_rec_time(frame)
        return frame

    def _fit_to_output(self, frame: np.ndarray) -> np.ndarray:
        image = Image.fromarray(frame)
        src_w, src_h = image.size
        dst_w = self.config.output_width
        dst_h = self.config.output_height
        scale = max(dst_w / max(1, src_w), dst_h / max(1, src_h))
        new_size = (max(dst_w, int(src_w * scale)), max(dst_h, int(src_h * scale)))
        image = image.resize(new_size, Image.Resampling.BILINEAR)
        crop_x = (new_size[0] - dst_w) // 2
        crop_y = (new_size[1] - dst_h) // 2
        image = image.crop((crop_x, crop_y, crop_x + dst_w, crop_y + dst_h))
        return np.array(image, dtype=np.uint8)

    def _apply_vhs(self, frame: np.ndarray, now: float) -> np.ndarray:
        h, w = frame.shape[:2]
        work = frame.astype(np.int16)

        # Low-resolution VHS softness.
        small_w = max(160, w // 3)
        small_h = max(120, h // 3)
        image = Image.fromarray(frame)
        image = image.resize((small_w, small_h), Image.Resampling.BILINEAR)
        image = image.resize((w, h), Image.Resampling.BILINEAR)
        work = np.array(image, dtype=np.int16)

        # Chromatic channel shift.
        shift = int(2 + 2 * np.sin(now * 1.7))
        red = np.roll(work[:, :, 0], shift, axis=1)
        blue = np.roll(work[:, :, 2], -shift, axis=1)
        work[:, :, 0] = red
        work[:, :, 2] = blue

        # Scanlines and analog noise.
        work[1::2, :, :] = (work[1::2, :, :] * 0.72).astype(np.int16)
        noise = np.random.normal(0, 9, work.shape).astype(np.int16)
        work += noise

        # Occasional horizontal tracking wobble.
        for y in range(0, h, 4):
            row_shift = int(np.sin(now * 4.0 + y * 0.035) * 2)
            work[y : y + 2, :, :] = np.roll(work[y : y + 2, :, :], row_shift, axis=1)

        work[:, :, 0] = work[:, :, 0] * 1.06
        work[:, :, 1] = work[:, :, 1] * 0.98
        work[:, :, 2] = work[:, :, 2] * 0.88
        return np.clip(work, 0, 255).astype(np.uint8)

    def _overlay_logo(self, frame: np.ndarray, now: float) -> np.ndarray:
        if self._logo is None:
            return frame

        h, w = frame.shape[:2]
        logo_w = int(w * 0.58)
        logo_h = int(logo_w * self._logo.height / max(1, self._logo.width))
        logo = self._logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        logo_arr = np.array(logo, dtype=np.uint8)
        alpha = logo_arr[:, :, 3].astype(np.float32) / 255.0
        rgb = logo_arr[:, :, :3].astype(np.float32)

        waved_rgb = np.zeros_like(rgb)
        waved_alpha = np.zeros_like(alpha)
        for y in range(logo_h):
            x_shift = int(np.sin(now * 2.2 + y * 0.055) * 5)
            waved_rgb[y] = np.roll(rgb[y], x_shift, axis=0)
            waved_alpha[y] = np.roll(alpha[y], x_shift, axis=0)

        opacity = 0.20 + 0.04 * np.sin(now * 1.3)
        overlay_alpha = (waved_alpha * opacity)[:, :, None]
        x0 = (w - logo_w) // 2
        y0 = int(h * 0.48 - logo_h / 2)
        region = frame[y0 : y0 + logo_h, x0 : x0 + logo_w].astype(np.float32)
        if region.shape[:2] != (logo_h, logo_w):
            return frame
        region = region * (1.0 - overlay_alpha) + waved_rgb * overlay_alpha
        frame[y0 : y0 + logo_h, x0 : x0 + logo_w] = np.clip(region, 0, 255).astype(np.uint8)
        return frame

    def _overlay_rec_time(self, frame: np.ndarray) -> np.ndarray:
        try:
            import cv2
        except Exception:
            return frame

        now = datetime.now(MOSCOW_TZ)
        if self.config.display_year:
            now = now.replace(year=self.config.display_year)
        time_text = now.strftime("%d.%m.%Y %H:%M:%S")
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (18, 16), (18 + 270, 54), (0, 0, 0), -1)
        cv2.putText(frame, time_text, (30, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)

        cv2.circle(frame, (w - 94, 35), 9, (255, 22, 0), -1)
        cv2.putText(frame, "REC", (w - 78, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 255, 255), 2)
        return frame

    def _publish_shared_frame(self, frame: np.ndarray, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_shared_publish < 1.0 / max(0.1, self.config.shared_publish_fps):
            return
        self._last_shared_publish = now
        try:
            tmp_path = self.config.shared_frame_path.with_suffix(".tmp.jpg")
            image = Image.fromarray(frame)
            image.save(tmp_path, format="JPEG", quality=90)
            tmp_path.replace(self.config.shared_frame_path)
        except Exception as e:
            logger.debug("Failed to publish shared HDMI capture frame: %s", e)

    def _touch_heartbeat(self) -> None:
        try:
            self.config.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            self.config.heartbeat_path.write_text(str(time.time()))
        except Exception as e:
            logger.debug("Failed to update video wall heartbeat: %s", e)

    def _show_frame(self, frame: np.ndarray) -> None:
        if self.config.output == "fbdev":
            self._show_frame_fbdev(frame)
            return
        if self.config.output == "pykms":
            self._show_frame_pykms(frame)
            return
        if self._screen is None:
            return
        import pygame

        surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
        self._screen.blit(surface, (0, 0))
        pygame.display.flip()
        if self._clock is not None:
            self._clock.tick(self.config.capture_fps)

    def _show_frame_fbdev(self, frame: np.ndarray) -> None:
        if self._fbdev is None:
            return

        h, w = frame.shape[:2]
        if w != self.config.output_width or h != self.config.output_height:
            frame = self._fit_to_output(frame)

        rgb = frame.astype(np.uint16, copy=False)
        red = (rgb[:, :, 0] >> 3) & 0x1F
        green = (rgb[:, :, 1] >> 2) & 0x3F
        blue = (rgb[:, :, 2] >> 3) & 0x1F
        rgb565 = ((red << 11) | (green << 5) | blue).astype("<u2", copy=False)

        self._fbdev.seek(0)
        self._fbdev.write(rgb565.tobytes())

    def _show_frame_pykms(self, frame: np.ndarray) -> None:
        if (
            self._kms_crtc is None
            or self._kms_plane is None
            or self._kms_fb is None
            or self._kms_fb_view is None
        ):
            return

        h, w = frame.shape[:2]
        if w != self.config.output_width or h != self.config.output_height:
            frame = self._fit_to_output(frame)
            h, w = frame.shape[:2]

        xrgb = np.empty((h, w, 4), dtype=np.uint8)
        xrgb[:, :, 0] = frame[:, :, 2]
        xrgb[:, :, 1] = frame[:, :, 1]
        xrgb[:, :, 2] = frame[:, :, 0]
        xrgb[:, :, 3] = 0

        row_bytes = w * 4
        raw = xrgb.reshape(-1)
        if self._kms_stride == row_bytes:
            self._kms_fb_view[: row_bytes * h] = raw.tobytes()
        else:
            for y in range(h):
                dst_start = y * self._kms_stride
                src_start = y * row_bytes
                self._kms_fb_view[dst_start : dst_start + row_bytes] = raw[
                    src_start : src_start + row_bytes
                ].tobytes()

        self._kms_fb.flush()
        plane_result = self._kms_crtc.set_plane(
            self._kms_plane,
            self._kms_fb,
            0,
            0,
            w,
            h,
            0,
            0,
            float(w),
            float(h),
        )
        if plane_result < 0:
            raise RuntimeError(
                f"Failed to set DRM plane {self._kms_plane.id} on {self.config.drm_connector}: {plane_result}"
            )
        if self._pykms_frame_count == 0:
            logger.info("First pykms frame shown on %s at %sx%s", self.config.drm_connector, w, h)
        self._pykms_frame_count += 1

    def _load_logo(self) -> Optional[Image.Image]:
        try:
            return Image.open(self.config.logo_path).convert("RGBA")
        except Exception as e:
            logger.warning("Failed to load video wall logo %s: %s", self.config.logo_path, e)
            return None

    def _placeholder_frame(self, t: float = 0.0) -> np.ndarray:
        h = self.config.capture_height
        w = self.config.capture_width
        yy, xx = np.mgrid[0:h, 0:w]
        base = np.zeros((h, w, 3), dtype=np.uint8)
        base[:, :, 0] = (18 + 28 * np.sin(xx / 42 + t)).clip(0, 255)
        base[:, :, 1] = (20 + 18 * np.sin(yy / 36 + t * 0.8)).clip(0, 255)
        base[:, :, 2] = (24 + 36 * np.sin((xx + yy) / 80 + t * 0.6)).clip(0, 255)
        if random.random() < 0.08:
            base[random.randrange(0, h), :, :] = (255, 255, 255)
        return base

    def _stop(self, *_args) -> None:
        self._running = False

    def _cleanup(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        if self._fbdev is not None:
            try:
                self._fbdev.close()
            except Exception:
                pass
            self._fbdev = None
        if self._screen is not None:
            try:
                import pygame

                pygame.display.quit()
                pygame.quit()
            except Exception:
                pass
            self._screen = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VNVNC CRT video wall renderer")
    parser.add_argument("--headless-test", action="store_true", help="render one test frame without display/capture hardware")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("VNVNC_VIDEO_WALL_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()
    config = VideoWallConfig()
    if args.headless_test:
        config.output = "headless"
    VideoWallRenderer(config).run()


if __name__ == "__main__":
    main()
