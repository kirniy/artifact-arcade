# STEP UP / BytePlus Flash

Theme `step-up`, menu/idle key `step_up`. Exact emblem from
`~/Downloads/STEP-UP-emblem.png`; campaign reference from STEP UP video project.
Cinematic trial B prompt retained. Native video source:
`/Users/kirniy/dev/VIDEOS/step-up/delivery/02-LED-FAN.mp4`.
Prepared silent H264/yuv420p128², full23.732042s at24000/1001fps; native looping.
Hashes pinned in theme and `assets/idle/step_up/manifest.json`.

Images use `ARTIFACT_IMAGE_PROVIDER=byteplus` and the fixed cheapest tested
model `dola-seedream-5-0-flash-260915`: published $0.018/output. Inline reference
images, one864x1536PNG per normal photo. One provider request; no automatic paid
retry, no Gemini/OpenRouter fallback. Existing Gemini credentials and old
providers/themes remain for rollback. The generated portrait still goes through
the existing deterministic footer, square-display crop, receipt and gallery QR.
No extra LLM/photo-analysis call is added. Text-only legacy modes are unchanged.

Activation: `sudo -n bash scripts/activate-step-up-photobooth.sh --restart`.
Reads an already provisioned private key from
`data/private/byteplus-modelark.key` (0600), or BYTEPLUS_MODELARK_API_KEY.
Validates hashes/video/menu before atomic .env update and uniquely named private
backup. Enables photo AI, selects BytePlus, disables OpenRouter fallback, selects
STEP UP theme/menu/default, preserves camera controls/HDMI-AI and hidden quest
entry/profile. Legacy quest QR printing stays disabled. Actual Tickets Cloud
ВСЕ СВОИ club nights retain their existing schedule override.

Deployment requires actual clean runtime inspection, a Git checkpoint, private
environment backup, paused updater restored by trap, fresh idle before patch
and an idle-gated restart. Never reset runtime or interrupt a guest.
Rollback at idle: revert this release and restore its exact `.env.before-step-up-*`
backup, then idle-gated restart. The key stays in a private ignored file, never
in Git/command output. Restore previous provider/AI flags through that backup.

QA:73 targeted local regressions passed; real integrated client/service/prompt
produced a valid PNG in17.66s on Mac. The prior four model trials took15–19s.
No physical print claim. Deployment status and exact Pi backup recorded after
actual device verification, not inferred from local readiness.
