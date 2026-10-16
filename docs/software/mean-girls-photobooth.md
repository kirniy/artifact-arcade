# MEAN GIRLS photobooth — 17 October 2026

## Scope and status

Prepared locally, **not installed on the live Pi**. `tailscale status --json`
reports `artifact` (100.115.122.91) offline, last seen 2026-10-16T03:25:35Z;
SSH to that IP timed out, `artifact.local` did not resolve. No live runtime,
current dirty files, current environment, physical ticker, camera or paper check
can be claimed. No guest messages, backend changes or live registrations made.

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

Activation sets `ARTIFACT_SPIDERVERSE_QUEST_ENABLED=false` and
`ARTIFACT_LEGACY_QUEST_PRINT_ENABLED=false`. Hidden quest code and data remain.
With printing disabled, even a stale Spider print payload produces only its
normal photo receipt, without its appended quest invitation/QR. A stale PARTY
EXAM print payload raises an explicit error before producing printable bytes.
Normal photo/gallery QR remains unchanged and decodes in tests. Restore flags
and the former profile from the private environment backup to re-enable the
old quest. The new contest/bot backend is owned by the VNVNC Bot thread.

## Activation and rollback

Prepared entry point: `scripts/activate-mean-girls-photobooth.sh [--restart]`.
It validates asset hashes, full video decode, format/duration/FPS, menu wiring,
and both fonts before touching the environment. Environment writes are atomic,
private backups are uniquely timestamped, and a second activation is a no-op.
Only theme/menu/default, fortunes-off, legacy-quest-off and the established
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
