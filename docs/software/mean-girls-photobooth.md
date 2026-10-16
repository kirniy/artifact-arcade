# MEAN GIRLS photobooth — 17 October 2026

## Scope and status

**Installed on the live Pi** at 21:07 Moscow, 16 October (client date 17 October).
Source commit `677dd9d` was cherry-picked onto the clean `artifact-runtime` as
`17fb002`. Pi initially was offline; it came online during final verification,
Tailscale SSH authentication completed, and fresh idle was verified before
installation and restart. No guest messages or backend changes were made.

Theme `mean-girls`, menu key `mean_girls`, idle variant `mean_girls`.
Electric magenta #F505F6, black/white/chrome UI; dark rose footer ink for paper.
Exact approved emblem from
`/Users/kirniy/dev/VIDEOS/Mean Girls 2/delivery/MATCHED-VENUE-FINAL/MEAN-GIRLS-emblem-transparent.png`,
resized with Clop to a 1024² transparent derivative. No redraw or replacement.
SHA pins and exact source hashes are in `assets/idle/mean_girls/manifest.json`.
Anton from the approved motion source, full SIL-OFL Unbounded for Cyrillic and
numbers. Impact is not redistributed. See `assets/fonts/mean-girls/README.md`.

Idle source is strictly
`/Users/kirniy/dev/VIDEOS/Mean Girls 2/delivery/APPROVED-VIDEOS/03-SPB-LED-FAN.mp4`.
Clop converted a separate copy to silent H.264/yuv420p 128², retaining all
15.056708 seconds at 24000/1001 fps. The existing elapsed-time/cached-frame player
loops it; no tenfold re-encoding or playback speed change. Originals untouched.

## Photographs and old quest

Activation preserves AI-enabled flags, local-photo flag, provider/model,
credentials, camera controls and camera selector. The existing offline photo
processing keeps complete real camera photographs and poses; only frame,
large emblem, header height and verified footer typography change for this
new theme. No silhouette segmentation, synthetic face shapes or extra API call.
A separate MEAN GIRLS AI style is wired for installations already using AI,
with exact emblem and identity crops. Its API contract is tested with a stub;
**no new paid/live AI rendering or visual likeness result is claimed**.

Legacy URLs:

- Static Spider Quest: `https://t.me/vnvncbattlebot?start=spiderquest`.
- PARTY EXAM: individualized
  `https://t.me/vnvncbattlebot?start=exam_<32-character claim_token>`.
  No single static EXAM URL exists; do not discard or rewrite existing tokens.

Activation preserves `ARTIFACT_SPIDERVERSE_QUEST_ENABLED` and
`ARTIFACT_QUEST_PROFILE` exactly. It sets only the independent
`ARTIFACT_LEGACY_QUEST_PRINT_ENABLED=false` print flag. Hidden quest code and data remain.
With printing disabled, even a stale Spider print payload produces only its
normal photo receipt, without its appended quest invitation/QR. A stale PARTY
EXAM print payload raises an explicit error before producing printable bytes.
Normal photo/gallery QR remains unchanged and decodes in tests. Restore the print flag from the private environment backup to re-enable
old quest printing. Entry and profile are independent and must not be changed
by event-theme activation. The new contest/bot backend is owned by the VNVNC Bot thread.

## Activation and rollback

Prepared entry point: `scripts/activate-mean-girls-photobooth.sh [--restart]`.
It validates asset hashes, full video decode, format/duration/FPS, menu wiring,
and both fonts before touching the environment. Environment writes are atomic,
private backups are uniquely timestamped, and a second activation is a no-op.
Only theme/menu/default, fortunes-off, legacy-quest-print-off and the established
Tickets Cloud schedule settings are set. Actual «ВСЕ СВОИ» events still override
MEAN GIRLS from 23:00 through 07:00 Moscow.

When Pi is online:

1. Inspect its actual repo/release type, branch, tracked/untracked changes,
   recent status timestamp, current safe idle, services and updater. Inspect
   only non-secret environment keys. Do not overwrite runtime work or stop a guest.
2. For a Git runtime, create a timestamped backup branch and private `.env`
   backup. Pause the actual update timer and restore it with a shell trap.
   Fetch `origin codex/mean-girls-photobooth` (or the accompanying Git bundle)
   and cherry-pick this release commit. Stop on conflicts; never reset the
   runtime to the development checkout. For release directories, compare hashes
   and back up each destination before copying only release files.
3. At fresh idle run
   `sudo -n bash scripts/activate-mean-girls-photobooth.sh --restart`.
   The existing idle-gated helper defers restart if occupied. Restore updater.
4. Verify live theme/menu/default and both quest flags, active services, fresh
   idle, full loop, all ticker journey states, camera and a real local/AI test
   appropriate to the retained runtime mode. Generate a thermal preview first;
   physical paper appearance requires onsite inspection. No fake registrations.
5. Roll back at idle: revert only the release commit and restore the exact
   private `.env.before-mean-girls-<timestamp>Z` file, then idle-gated restart.
   Do not reset or discard later unrelated runtime changes.

## QA receipt

Local tests cover exact assets, menu/style/reference routing, identity contract,
full idle decode/cache/loop, retained old themes and quest, complete offline
source corners, real-photo result, typeface coverage, activation idempotence,
private rollback backup, unchanged AI/camera settings, stale quest print block,
normal QR decoding and Tickets Cloud scheduling. Preview files:
`output/mean-girls/real-guest-preview.png` and `receipt-preview.png`.
No physical print was sent.

One pre-existing broad test is excluded explicitly:
`test_every_theme_idle_label_fits_and_is_static` fails on the old raw
`PROJECT X` label (53px versus 48px); `git show` confirms it predates this release.
MEAN/GIRLS/ФОТО labels are each tested to fit 48px. This release does not alter
PROJECT X behavior. The deployment must not claim an entirely green global suite.

## Live verification receipt

- Both `artifact` and `arcade-autopull.timer` active; tracked runtime clean.
- Startup log: loaded MEAN GIRLS idle video, registered exactly one photobooth
  mode, and registered the IMX708 camera. No camera-source/settings changes.
- Live selector/menu and both retired-quest flags verified. AI=false,
  local-photo=true, HDMI-AI=false retained from the pre-install runtime.
- All 361 idle frames decoded on Pi. Real saved source rendered through the
  actual local photo method in 1.2 seconds, returning a 720×1022 print image.
- Normal gallery QR decoded; stale Spider appendix suppressed; PARTY EXAM
  printing rejected while disabled. Thermal payload: 68,850 ESC/POS bytes.
- USB RP80 absent, `/dev/usb/lp0` absent: no physical paper test sent or claimed.
  No live AI API generation requested. Physical ticker stability is not observed.
- Backup branch: `backup/before-mean-girls-20261016T210645`.
- Exact private activation backup on Pi:
  `/home/kirniy/modular-arcade/.env.before-mean-girls-20261016T180650223907Z`.
- Additional private runtime backup:
  `data/deploy_backups/mean-girls-20261016T210645/runtime.env`.
- Actual Pi previews copied to Mac:
  `output/mean-girls/pi-live-preview.png` and `pi-live-receipt.png`.
- Local verification: 80 passed, one pre-existing PROJECT X width test deselected.

## Correction: preserve the independent hidden quest entry

The owner requested restoring exactly the pre-MEAN-GIRLS hidden-entry setting.
`ARTIFACT_SPIDERVERSE_QUEST_ENABLED` must be `true`; the existing profile remains
`party_exam`. The original installation's `false` entry setting recorded above
was corrected separately. The activation script no longer writes this key at
all; tests cover enabled, disabled and absent values. The independent print
flag remains `false`, so restoring entry does not resume quest QR printing.
No SpiderQuest URL, bot routing, old quest data, theme, idle, camera or AI
settings are changed by this correction.
