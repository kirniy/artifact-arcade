# Project X photobooth — prepared 16 September 2026

Deployment: **17 September 2026, 19:00 Europe/Moscow, one attempt**, together with PARTY EXAM. No deployment or Pi contact performed during preparation.

## Theme

`PHOTOBOOTH_THEME=project-x`, `PHOTOBOOTH_MENU_MODES=project-x`, enable the date-aware schedule with `ARTIFACT_CLUB_THEME_SCHEDULE=project-x-2026` (the older weekly script defers to it). Keep `ARTIFACT_QUEST_PROFILE=party_exam` and `ARTIFACT_SPIDERVERSE_QUEST_ENABLED=true`: long-press 7 remains the separate exam mode. Do not change image-provider credentials/settings.

Four randomly selected college-party scenes: cup-pong victory, pep rally, dorm-room cup trophy, fraternity lawn party. Identity crops preserve the original guests; costumes change to varsity/jersey/cheer outfits. Exact canonical emblem copied from VIDEOS/project-x/work/emblem-front-alpha.png, pinned by SHA256. White background, pale costumes, small blue/red accents, high-key faces, no dark frame. Existing white footer renderer supplies verified venue/day/time; club night rolls over at 07:00.

## Prepared files and installation

`output/project-x/release/manifest.json` checksums the new prompt module, emblem, tests and integration.patch. This patch captures the current working versions of the three shared photobooth files, including earlier local theme work. **It is a review artifact, not a blind overwrite package.** On the Pi inspect the live versions and uncommitted changes first. Use `git apply --check`; if it does not apply, port only the Project X additions into the live files, preserving its existing themes. The earlier Tropical Thai implementation is a dependency of this local baseline and must not be accidentally removed or copied incompletely. Back up all edited files and .env. Stop the updater only during the verified installation; restore its previous state. Follow PARTY EXAM's idle guard and rollback procedure.

Project X additions: two CaricatureStyle members; isolated generate_project_x dispatcher; theme registration and canonical emblem; menu aliases; identity reference pass-through; white footer; upper square-safe display crop. Existing PARTY EXAM package remains separate and unchanged.

## Validation and physical canary

Run `PYTHONPATH=src .venv/bin/python -m pytest tests/test_photobooth_project_x.py tests/test_party_exam.py -q` where test dependencies exist. New service tests use a fake image provider and verify routing, aspect ratio, original photo + emblem + identity references, missing-emblem rejection, four scenes and 07:00 rollover.

AI art direction is probabilistic: these tests do not prove likeness or thermal-print quality. Before opening the booth, make a consenting operator capture, inspect every face and actual generated brightness, then print one RP80 receipt. Verify faces, emblem, footer, QR and all subjects in square preview. If generation is too dark, correct the prompt before guest use. Actual camera, generation and paper output remain pending device access.

## Live generation test and camera audit, 16 September

Real configured Vertex gemini-3.1-flash-lite-image tests: two successful original scenes in 8.1/8.7 seconds, 768×1376. Exact ESC/POS raster decoded for review: 16.6% /14.1% black pixels. Results under output/project-x/live-test. User approved both close portrait and full-body composition; retain both. A later test with three face crops succeeded in7.4seconds; the following call exhausted provider quota (429), so availability is not proven for the event. Verify quota before opening. Test images were not published/uploaded to gallery.

Camera audit identified hardware resolution argument missing (640×480 default despite service's2048×1536), RGB888 interpreted as RGB though Picamera2 yields BGR bytes, destructive fixed channel multipliers, and no explicit autofocus. Prepared fixes in hardware/camera/picamera.py and utils/camera_service.py: pass2048×1536, selectBGR888 for RGB arrays, retain unmodified channels, enable supported Continuous autofocus. ARTIFACT_CAMERA_EXPOSURE_EV is an optional bounded[-2,2] on-device tuning control; no guessed fixed exposure applied. Unit tests use a fake sensor. Hardware validation pending; include these two files in reviewed backup/patch installation, never blind overwrite.

Next physical camera tuning: inspect actual ExposureTime/AnalogueGain/AfState under club lighting; test short shutter against available face illumination. A soft neutral fill light near lens is preferable to reconstructing clipped or motion-smeared faces. Do not introduce inferred depth or generative face restoration as identity evidence. Burst selection is a potential follow-up, not implemented or claimed tested; selection must score every face, not sharp background decorations, and keep originals.


## Approved automatic schedule

Set ARTIFACT_CLUB_THEME_SCHEDULE=project-x-2026 during installation. The Python schedule owns both current theme and menu, overriding stale .env selections: before18September2026 07:00 Moscow → vse-svoi; from that instant until20September2026 07:00 exclusive → project-x; afterwards → vse-svoi. This is a specific dated weekend, not all future Fridays. It evaluates wall-clock time at startup and while running. Safe idle/menu update replaces photobooth registrations and refreshes idle art/menu. Active guest, prize drum and exam sessions finish before changing. Power cycles need no stored last-theme state. The Pi clock must be correct: verify timedatectl synchronization before opening. Include club_theme_schedule.py and review schedule-integration.patch alongside existing PARTY EXAM manager additions; do not apply conflicting full patches blindly.

User supplied three additional640×480 photos showing strong motion smear and red/magenta saturation. Keep these as camera canary examples; no depth inference or AI restoration claimed to recover original facial detail.


## Implemented fresh-burst quality selection

Photobooth primary capture now calls capture_best_jpeg: up to3 fresh full-resolution requests, stops requesting additional frames after0.8seconds elapsed, retains only best pixels in memory plus small diagnostic metadata. A single native sensor request can still block according to sensor timing; there is no unsafe competing camera thread or artificial promise of a hard timeout. Picamera2 queue=False avoids using a pre-trigger cached still. Each request is released in finally. JPEG95 with no chroma subsampling. Supported AeExposureMode.Short prefers short automatic shutter times while leaving gain automatic. All controls remain subject to hardware canary.

OpenCV Haar detection at max640px width, Gaussian-prefiltered Laplacian sharpness on96px face regions, clipping/dark penalties, weakest-face score; detected face count takes precedence. Detection can miss faces under extreme lighting, so no-face fallback evaluates the central guest region. This is heuristic selection, not a guaranteed recognition model. Partial failures retain a successful frame; zero successful frames returnsNone. No generative restoration, depth inference, frame fusion or extra AI request. Existing identity crops derive from the selected original. Diagnostics report index/face count/quality/exposure/gain/focus/sensor timestamp. Camera audit JSON under output/project-x. New capture_quality.py is required alongside reviewed camera-quality.patch and integration.patch.

Research: official Picamera2 request/metadata implementation and examples (github.com/raspberrypi/picamera2); OpenCV CPU image processing already in hardware dependencies. No extra heavy runtime dependencies or model downloads.

Audit limitation: Haar reports3boxes on the supplied two-woman image (false positive), demonstrating detection is heuristic. Do not claim exact guest-count recognition from quality diagnostics. Pin OpenCV hardware dependency<5 because local5.0 build lacked CascadeClassifier. All28 focused camera/schedule/theme/exam tests passed.


## Latency requirement supersedes automatic burst

User requires no added guest wait. Default ARTIFACT_CAMERA_BURST_ENABLED=0 uses the original single capture path, with JPEG95 and camera resolution/focus/color fixes. It performs no additional capture/scoring wait. Burst implementation remains opt-in only; do not enable during installation until real hardware timing is measured and approved against guest latency. No claim of background countdown capture implemented: capturing before preflash would sacrifice illumination, and locking a live burst during countdown could delay final capture. Extra AI calls remain zero. Default path latency guard tested;11focused tests passed. Higher-resolution acquisition/encoding/provider transfer may still change total latency; do not promise identical end-to-end timing without Pi measurements.


## Final user correction: background burst enabled automatically

This supersedes the opt-in/default-single section. Burst now enabled without any flag: Photobooth starts CountdownCapture during the final second of the existing countdown. Worker publishes each improving encoded candidate to a session-local snapshot. At shutter/AI transition, stop additional burst requests and use the best already-ready JPEG immediately, without waiting for a later sensor request or scoring. If no candidate yet, poll nonblocking on subsequent UI updates until first candidate or failure; unavoidable sensor latency may exceed countdown, but never waits for all3frames. Worker errors cannot leak an older session's photo. on_exit signals stop; worker never mutates mode state. At most one camera acquisition owner under existing camera lock. All captures before final preflash can have less screen illumination than the original shutter capture; performance/lighting tradeoff is explicitly pending hardware validation. No claim of hard sensor timeout or guaranteed zero end-to-end delay. New countdown_capture.py is mandatory installation payload. Simulated slow-second-frame verifies snapshot returns without waiting; separate sessions and partial failures tested.


## Approved Project X idle video

Source /Users/kirniy/dev/VIDEOS/project-x/telegram/02-LED-FAN-SOUND-H264.mp4 (960square,15seconds). Installed asset assets/idle/project_x/video/project-x-fan-10x.mp4: ten repeats,150seconds,128square,H.264 baseline,yuv420p,24fps,2131887bytes. Audio removed to preserve the booth's existing idle music ownership. Runtime repeats indefinitely, time-based frame reuse at high UI refresh rate; loop boundary and whole-filedecode tests passed. Project X required idle filename is registered; blue UI accent65/145/255, blue ticker0/160/255. Deployment payload includes this video plus idle-integration.patch. Include prior shared-theme dependencies in a reviewed branch checkout, preserve live work. Source video is not committed.
