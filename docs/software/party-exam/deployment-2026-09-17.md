# PARTY EXAM and Project X deployment — 17 September 2026

Verified on the actual `artifact` Raspberry Pi at 21:59 Moscow time.
The software is installed and running. Physical receipt printing remains
unverified because the RP80 is not enumerated on USB.

## Source and installed revision

The requested source conversation was
`codex://threads/01a0a6f3-08f0-7023-a40c-664ba5e62cbe`.
Its prepared release was `f868eacdb8718f8de8fe14a0451133e759ac21ee`.
The additional idle-schedule correction is source commit `4f16695` on
`codex/project-x-party-exam-ready`. Outage-safe offline PARTY EXAM issuance is
source commit `02e2b63`; the matching backend implementation is
`5b7a7153` in the VNVNC bot repository.

Machine: Raspberry Pi 4 Model B Rev 1.5, hostname `artifact`, Tailscale
`100.115.122.91`, checkout `/home/kirniy/modular-arcade`.
The installed runtime branch is `artifact-runtime` at merge commit
`128ee37eab90514cd0a7fa5ce8fa62ea88e93136`.

The previous runtime was `4606c21`. Before merging, the existing Vertex
Express routing edit and local Sunset Palms files were preserved in
machine-local checkpoint `7015c148015391170b5c2a136c9fd71ddab03ab3`.
The prepared release was merged into that runtime rather than replacing
the checkout or restoring the repository's large archive assets.

## Enabled behavior

PARTY EXAM is selected by holding numpad 7 for two seconds. The numpad 9
prize-wheel path remains unchanged. The exam uses a private portrait,
student document and permanent personalized Telegram claim link.

`ARTIFACT_CLUB_THEME_SCHEDULE=project-x-2026` controls the photograph theme,
menu and idle screen. All boundaries below use Europe/Moscow:

| Period | Photobooth theme |
| --- | --- |
| Before 18 September 2026, 07:00 | ВСЕ СВОИ |
| 18 September 07:00 through 20 September 06:59:59 | Project X |
| From 20 September 2026, 07:00 | ВСЕ СВОИ |

The runtime waits for a safe idle/menu state before switching themes.
Project X includes its approved emblem, 128×128 H.264 idle loop and
white-background receipt artwork. The primary camera uses 2048×1536
capture, supported autofocus controls and a background countdown capture.

Only these configuration keys changed: `ARTIFACT_CLUB_THEME_SCHEDULE`,
`ARTIFACT_QUEST_PROFILE`, `ARTIFACT_SPIDERVERSE_QUEST_ENABLED`,
`PHOTOBOOTH_MENU_MODES` and `PHOTOBOOTH_THEME`. The remaining configuration
and the existing provider-routing file were compared with the backup and
confirmed preserved.

PARTY EXAM receipt issuance is now local-first. Before printing, the Pi
atomically reserves a student number from a pre-provisioned range and creates
a 32-character signed Telegram claim token in its private SQLite store. No
backend request is on the print-critical path. A local grayscale portrait is
saved before the bounded AI attempt, so an AI or network outage still leaves
a printable portrait and permanent personalized QR. An independent
`artifact-party-exam-sync.service` uploads finalized portraits later with
idempotent retry/recovery semantics.

The backend reserves durable 100,000-number blocks to authenticated kiosks.
The `artifact` Pi currently holds `26091841` through `26191840`; the server
allocator has advanced to `26191841`. Replaying the same allocation request
returned the same range. Provisioning created no student row. The backend can
materialize a signed offline card when the Telegram QR is scanned before its
portrait arrives, then attach the later portrait to the same identity. Claims
or stamps that serialize after a completed 04:00 draw cannot retain an earlier
timestamp and therefore cannot become retroactively eligible.

## Findings corrected during deployment

The two original installation patches overlap in `manager.py`; they must
not be blindly applied in sequence. The consolidated Git release was used.
The actual updater is `arcade-autopull.timer`, not the name assumed by the
old one-package installer. Its state was preserved and restored.

A live startup check found that the idle video still preferred the stored
`PHOTOBOOTH_THEME` over the dated schedule. This could select a video slot
that did not belong to the active theme. Commit `4f16695` makes the schedule
take precedence there too and adds four regression tests. The final theme,
menu and idle variant all resolved to ВСЕ СВОИ at verification time.

## Verification performed

The 95-test release/regression suite passed on the Mac and against the
merged candidate on the Pi. After the idle correction, 33 affected checks
passed on both machines, including the four new regression tests.
Friday/Saturday receipt rendering, QR decoding, private persistence,
print-error recovery, shared-input behavior, theme boundaries, upload
recovery and printer-device detection are covered by those checks.
Both prepared package manifests passed checksum verification.

The offline receipt suite passed 45 focused tests on both the Mac and the
actual Pi. Coverage includes a forced network failure while rendering and
decoding the personalized QR, bounded AI timeout with the local portrait
already durable, identical reprint identity after restart, allocation
recovery, lost upload acknowledgement, first-portrait-wins synchronization
and outbox retry ordering. The backend passed 35 focused tests. Disposable
PostgreSQL checks also passed concurrent same-ID allocation, non-overlapping
allocation ranges, scan + sync + draw serialization, the existing concurrent
online-card/draw suite, and an upgrade/downgrade/upgrade of the additive
offline allocation migration.

A fixed cross-repository token vector matched byte-for-byte on booth and
backend. A separate disposable integration test generated a card with the
booth implementation, claimed it in the backend before portrait sync, and
then synchronized the portrait onto the same issue ID, student number and
owner. On production, the authenticated provision route replayed the same
range and the authenticated sync route rejected an invalid signed probe as
`INVALID_CARD`. Production still had zero PARTY EXAM students after these
checks.

A real IMX708 camera capture produced a valid 2048×1536 JPEG. The first
usable candidate arrived in 666.2 ms and retrieving the ready frame took
0.006 ms. The worker completed and the camera closed cleanly. These are
single-canary timings, not a guarantee for every lighting condition.
The full-resolution canary image was not saved or uploaded.

The configured Vertex image model generated the exam portrait from an
existing approved test photo in 7.43 seconds. Its 896×1200 JPEG was decoded
and visually inspected. This was a private AI test, not an exam registration.
An authenticated empty-portrait request to `/api/party-exam/issue` returned
`INVALID_PORTRAIT`, verifying device authentication without creating a
participant. The public exam Mini App returned HTTP 200.

At final verification, `artifact`, `artifact-party-exam-sync`, `arcade-bot`,
`artifact-upload-spool` and the updater/clock/schedule timers were active.
Runtime status was less
than one second old, the tracked worktree was clean, and the automatic
updater had completed with exit status 0. The existing HTTPS clock fallback
reported offsets within 0.3 seconds; NTP's synchronized flag remained false.

## Remaining physical check

The RP80 was absent from `lsusb` and no USB printer device node was present.
The exam print path explicitly requires an RP80 and must not report a
successful receipt through the label-printer/mock fallback. Real paper
output, cutter operation and scanning the printed QR remain unverified.
Power/connect the RP80 before performing that canary. No fake participants,
giveaway draws or public photo uploads were created during deployment.

## Recovery and evidence

Private backup directory on the Pi:

`/home/kirniy/.local/share/artifact-deploy/project-x-20260917-214356`

It contains the original environment and affected files, dirty patch,
service definitions, merge and test logs, activation records, physical
camera diagnostics, private model-probe output and `verification.json`.
Keep this directory private; it includes the configuration backup.

The validated candidate checkout is retained under
`/home/kirniy/.cache/artifact-deploy/project-x-20260917-214356`.
The private AI preview is also available on the Mac under
`output/project-x/deploy-20260917/model-probe-portrait.jpg`.

The backend was deployed to `/opt/vnvnc-bot` only after the live copies of all
modified existing PARTY EXAM files matched their reviewed source baselines
byte-for-byte. The additive database migration is at
`20260917_party_exam_offline`; `vnvncbattlebot.service` is healthy. The
pre-deploy server backup is
`/opt/vnvnc-bot/.backups/party-exam-offline-20260917T194325Z`.
Existing participant, prize, gifting and giveaway state was left intact.
