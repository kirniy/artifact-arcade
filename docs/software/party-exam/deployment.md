# PARTY EXAM — readiness and deployment handoff

Updated 16 September 2026. The user's later changes override the colleague screenshots.

## Confirmed operation

- Friday 18 Sep 23:00 → 19 Sep 07:00 Moscow: one final host QR / one credit at КХ photo zone. Registration alone is not eligible.
- Saturday 19 Sep 23:00 → 20 Sep 07:00: three faculty credits then the separate Кринжология exam; four host scans required.
- Both draws: 04:00. Late stamps remain visible but are excluded. Separate pools and three distinct winners per night, persisted once. Fewer than three eligible guests means fewer winners, no duplicate winner.
- Hold keypad 7 for two seconds selects the existing hidden quest gate, using `ARTIFACT_QUEST_PROFILE=party_exam`. Hold 9 is unchanged.
- Personal permanent Telegram claim link binds the privately saved portrait and sequential ID. IDs start 26091841 and advance across both nights. One user per night, no duplicate entry from another receipt.
- Shots are physical host-issued chips valid only until 07:00 that night.

## Installed backend

Host `root@82.38.148.239`, `/opt/vnvnc-bot`, `vnvncbattlebot.service`.
Mini App: https://api.vnvnc.ru/api/party-exam/book . This uses the existing API proxy and avoids redeploying an older local CDN wheel bundle. The wheel remains at its existing URL.
Migration `20260916_party_exam` applied. Two night rows, no test registrations, awards or deliveries in production. Background scheduler enabled. Stamp secret generated on the server and retained only in its environment. Admin and venue configuration checked.
Backup: `/opt/vnvnc-bot/backups/party-exam-20260916-011215`.
Frozen release: `/Users/kirniy/dev/modular-arcade/output/party-exam/server-release`.
The production webapp handler was patched from its live version, preserving newer referral/route changes. Do not replace it with the local repository's stale whole file.

Generic generated crest, cursive signature, leather and two ink stamps are public assets. Student photos are database/private filesystem data, never public assets or gallery objects.

Automation `party-exam` runs ONCE on17September2026 at19:00Europe/Moscow. It must pause after that single attempt, successful or not. No15-minute checks or automatic retry schedule.

## Pending Raspberry Pi deployment — already authorized

Latest explicit user instruction: install only tomorrow17September2026 at19:00Moscow, one attempt. Finish all non-hardware QA now. Do not ask again for installation permission.
Targets: `kirniy@100.115.122.91`, then `kirniy@artifact.local` if needed. Connection timeout8–10seconds; report unavailable hardware at the scheduled one-time attempt, then pause.
Package: `/Users/kirniy/dev/modular-arcade/output/party-exam/pi-release`.
Guarded installer source: `scripts/install-party-exam-package.py`; packaged as `install.py`.

1. Read this handoff and the repo AGENTS.md. Check the installed server health and the frozen package hashes.
2. When Pi is reachable, inspect its current branch, dirty diff, systemd units, `.env` key presence (never log values), camera and RP80 detection. Inspect `artifact-update` service/timer and its actual script: ensure it will not hard-reset away the installed patch. Resolve this before deployment without overwriting unrelated Pi work or changing its existing image provider/theme.
3. Do not interrupt a guest. Require fresh idle status or stopped application. Transfer the package into a private cache directory outside the checkout.
4. Run `.venv/bin/python /path/to/package/install.py --repo /home/kirniy/modular-arcade`. It checks the patch, backs up files/environment, applies only the three integration changes plus two modules and generated receipt assets, probes RP80 and an authenticated empty-portrait request that must be rejected (no student created), enables the hold-7 profile, restarts, and rolls back files on failure.
5. Verify service health/logs, feature environment, deployed file hashes and hold-7 activation while idle. Run `PYTHONPATH=src .venv/bin/python scripts/check-party-exam.py --hardware`.
6. Perform a camera/AI/thermal canary while idle. Before event hours, do not bypass campaign dates or create fake production participants: generate a private portrait and a clearly labeled TEST receipt through the normal printer path. Check the actual photo/generation output and USB print completion; physical paper appearance still needs an on-site look. Record what was and was not verified. Never call a successful USB write proof of paper quality.
7. Keep the old files/environment backup and ensure auto-update preserves the feature. Document the installed revision/patch and result here. On material failure, restore and report the failure; pause the automation and do not create automatic retries.
8. Notify the user only on successful install, actionable failure or required physical check. Pause the heartbeat after this single19:00attempt regardless of outcome. Do not send Telegram messages manually as part of installation; Telegram actions require the configured mcporter MCP and explicit recipient authorization.

## Recovery behavior

Source photo, generated portrait, issue ID and server response are written atomically to private files. Network retries reuse the same ID and portrait. On process restart, a recent unprinted job is shown for operator-confirmed retry. Printer errors keep the document; red button retries it. `#` abandons that local job. Reprints never create another giveaway entry. A USB write interrupted after paper output can leave an ambiguous physical print; the operator confirms the retry rather than automatic duplicate output.

Telegram notifications use a durable retry queue; failure for one recipient does not block others. Prize award/draw transactions are idempotent. Telegram itself cannot guarantee exactly-once messages across a crash after delivery but before database commit; such a crash may duplicate a notification, not the prize.

## Prizes and future events

Deposit: next three venue-filtered ВСЕ СВОИ club nights. Other prizes: next two other club nights. Event IDs and windows are persisted from TicketsCloud announcements. Unannounced future dates do not expire prizes. Redeem only during an allowed event window; gifting preserves the original entitlement and expiration. Multiple listings within one club night count once, including after midnight. Existing gifting limits still apply.

## Verification evidence

- 7 kiosk tests + 11 existing Spider tests passed: personal QR decode, private storage/no gallery, single queued job, hold-7 profile, printer retry, recovery after restart, retry without regenerating portrait.
- 17 backend tests passed: club-night boundaries, identity ownership, one/four required stamps, draw cutoff, repeated draw, gift acceptance and one-time redemption, future-event validity, failed-recipient delivery isolation.
- Disposable PostgreSQL: concurrent issue/claim retries and three parallel draws produced exactly three coupons; actual migration upgrade/downgrade/re-upgrade and schema checked.
- Chromium: 320×700 and 390×700, both night profiles, visible generated assets, stamp slots remain within paper, native scanner shim, denied scan produces no stamp, blue native header, four-stamp completion.
- Existing wheel/Spider/slots regression set: 143 passed, one unrelated `test_officecore_tab_closer_hard_award_is_once_per_week` fails identically on clean HEAD (cocktail limit precedence). No unrelated fairness change made.
- Exact production dependency imports and merged route setup passed. Public gradebook matches the local file; unauthenticated state returns 401. Two configured nights, zero production test participants/awards. A production signed kiosk probe accepted authentication, rejected the empty portrait and denied a repeated nonce; no student was issued. All five generated public assets match production hashes; all five private host QR cards decode to the intended night and stage.
- Physical Pi camera, AI and paper checks are pending power/network access. No claim of zero bugs or complete hardware verification.

## Operator assets

Private host cards: `output/party-exam/private-host-codes/` and `output/party-exam/party-exam-host-codes.zip`. They contain signed QR values: give only to hosts, do not publish in the channel or gallery. One Friday card and four Saturday cards. Guests scan with the Mini App's ПОЛУЧИТЬ ОЦЕНКУ button.
Visual previews: `output/party-exam/gradebook-390.png`, `gradebook-complete-390.png`, `gradebook-friday.png`, `receipt-2026-09-18.png`, `receipt-2026-09-19.png`. Sample portraits are schematic placeholders, not AI portrait quality evidence.

## 16 September readability follow-up

Installed a compact next-step screen and shorter bot greeting; full gradebook and rules open on request. Scanner CTA fits the first 320×700 viewport. Generated stamp toast confirms successful scans. Browser regression verifies that a delayed pre-scan state refresh cannot overwrite a newer stamp. The two-file server backup is `/opt/vnvnc-bot/backups/party-exam-short-copy-20260916-012948`. Shortened receipt renderer is in the frozen Pi package with an updated checksum; QR decode tests passed again.

Moscow implementation is owned by task `01a09b61-0da6-72e1-b2bb-fdd17978728a` in `/Users/kirniy/dev/vnvnc-msk-prohodka`. It has a common entrance QR, four separate stations both nights, FULL PASS with existing Moscow semantics plus deposits15k/10k/5k valid21days, and night-specific host codes. Do not deploy Moscow changes from the SPb release.

## Inline stamp correction

User rejected the floating stamp toast. SPb now reveals the actual ledger row and impresses the generated ink image directly into its slot, with paper recoil and native impact haptic. Final completion triggers a finite blue/gold confetti burst. Replays do not reanimate; reduced-motion disables movement and confetti. Chromium tests passed at320/390px including replay, stale state and reduced-motion. Public HTML byte-matches local. Static-only atomic deployment backup: `/opt/vnvnc-bot/backups/party-exam-inline-20260916-014252`; no service restart required. Moscow owner is applying the same correction.

## Moscow release completed

Moscow owner deployed commit `2b32cd8` to `/opt/vnvnc-msk-bot/current`; migration0058,22file hashes and healthy service verified. Backup: `/opt/vnvnc-msk-bot/backups/20260916-party-exam` (files, database, manifest). Public Mini App: https://vnvnc-msk-wheel.vercel.app/party-exam?v=20260916-exam . Entrance: https://t.me/vnvncmskbot?start=partyexam . Parent independently byte-compared public HTML/JS against local.

Print package: `/Users/kirniy/Downloads/VNVNC-MSK-PARTY-EXAM.zip` — one public A6 entrance sticker and four private host QR cards per night, PNG/PDF. Owner decoded all9PNGs and9independently rasterizedPDFs; parent checked ZIP integrity. Full owner receipt: `/Users/kirniy/dev/vnvnc-msk-prohodka/docs/releases/2026-09-16-party-exam.md`.

Owner verification:111regression and15focused tests passed; browser replay check passed. Parent independently verified four inline stamps, finite confetti, no overlay and no overflow in WebKit26.6 at320×700; SPb full browser suite also passed WebKit320/390 including reduced motion. Real owner Telegram initData read-only state accepted on origin/CDN, zero production exam entries/stamps/deliveries. Physical native camera/haptics still require a phone check. Moscow dates follow the requested SPb analogy18/19September,04:00; update if user supplies different dates. FULLPASS retains existing30entries owner+guest until31Dec2026; deposits15k/10k/5k expire21days after each draw.

## Final QA handoff

See `qa-2026-09-16.md` for final checks, actual Telegram preview IDs, giftability fixes, source-specific corrected gift artwork and remaining hardware checks. SPb latest static backup `/opt/vnvnc-bot/backups/party-exam-followup-20260916-023802`; gift runtime backup `/opt/vnvnc-bot/backups/party-exam-gift-theme-20260916-023234`. The only installation attempt is17September2026 at19:00Moscow; do not reinstate15-minutepolling.

Project X installation instructions: ../project-x-photobooth.md. Include this separately prepared theme without disabling PARTY EXAM.

Latest schedule authorization: enable ARTIFACT_CLUB_THEME_SCHEDULE=project-x-2026 on installation; follow ../project-x-photobooth.md. It selects ВСЕ СВОИ until18Sep07:00, Project X until20Sep07:00, then ВСЕ СВОИ. Keep exam gate enabled.
