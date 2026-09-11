# TROPICAL THAI photo booth

Theme `tropical-thai` / menu aliases `tropical-thai`, `tropical_thai`.

The supplied `VIDEOS/tropical-thai/references/tropical-thai-emblem.png` is copied
unchanged and hash-pinned. Image 1 supplies guests and clothes, Image 2 supplies
the emblem, and subsequent images are crops of the same guests. The dedicated
prompt offers four bright Octane-style Thai lagoon/jungle/orchid compositions,
with exact clothing and identity preservation. The normal booth pipeline keeps
face crops, vertical output, square display crop, verified footer and uploads.

Idle uses `TROPICAL-THAI-VIDEOS/02-LED-FAN.mp4`, the approved fan delivery, repeated
ten times without added graphics or fades. The output is H.264, 128×128, 24 fps,
yuv420p, silent, approximately 150.58 seconds. The source SHA-256 is pinned in
`scripts/prepare-tropical-thai-idle-video.sh`. Playback follows elapsed time so
screen refresh rate does not speed up the movie. It repeats while idle.

Activation: `scripts/activate-tropical-thai-photobooth.sh --restart` on the Pi.
Preflight validates full video decoding, dimensions, duration, emblem hash,
imports and compilation before atomically updating `.env`. It disables
`ARTIFACT_SPIDERVERSE_QUEST_ENABLED` and pauses weekly theme changes via
`ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED=0`. Provider credentials and upload
settings are preserved. Restart uses the existing idle-only helper.

Local verification: 24 tests covering new theme, aliases, canonical references,
provider routing, clothing rules, video timing/looping, missing-video preflight,
quest-off activation, existing menus, face gate and weekly schedule. Separately,
existing Sunset Palms / birthday regression tests passed in the original checkout.
A synthetic two-adult image is used for provider QA, never private guest captures.

Deployment evidence and final hashes are recorded alongside this document once
activation is verified. Keep the machine-local AI client patch intact.
