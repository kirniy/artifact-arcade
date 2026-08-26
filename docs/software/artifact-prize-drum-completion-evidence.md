# ФОТОБУДКА ВИНОВНИЦЫ prize drum — completion evidence

Updated: 26 August 2026 (Europe/Moscow)

Overall verdict: **local integration ready for owner review; not production-ready and not deployed**.

## Proven locally

- KP9 fires exactly at 2.0 seconds, requires release, and never leaks a capture digit.
- Hidden-mode entry/exit is exclusive; unsafe exit is deferred.
- Main display remains non-black across hidden-mode entry/exit and selector camera restoration.
- KP4 selects Telegram, KP6 selects guest, and the selected flow persists without retaining identity.
- A failed final server logout retains the same pending session, preserves the prize QR, blocks the next guest/exit and retries until acknowledged.
- Spin matrix is guest/auth-no-boost/one-boost/two-plus-boost = `1/1/2/3`.
- Backend chooses the prize; a committed request retried after timeout returns the same award.
- 60-spin local issue/retry/mock-RP80 preflight produced 60 unique awards/codes/prints and no print errors.
- Ordinary wheel cooldown, stock, limits, stats and boost consumption exclude `Spin.source=artifact_kiosk`.
- Ordinary prizes expire at 07:00 MSK; `TIX1FREE` has a dated full Fri/Sat pair and one atomic redemption.
- Two concurrent scanner redemptions yield one success and one `ALREADY_REDEEMED`.
- Authenticated awards enter the existing chest and create one durable personal Telegram outbox row; guest awards do not.
- Personal message includes prize, code, expiry/pass dates, chest copy, and exact `https://t.me/vnvncbattlebot?start=wheel` link.
- Admin payload includes prize, code, source, expiry and pass dates. Its durable outbox is acknowledged only after at least one Telegram admin delivery returns a message ID; no recipients, bad token and all-recipient failure remain retryable.
- Pending OIDC attempts are invalidated on Telegram→guest and session finish; callbacks require the exact sole active attempt and a pristine Telegram `auth_pending` session.
- Receipt uses VNVNC Classic logo, raw coupon QR, and exact regular-wheel QR. The redemption block explicitly says to show it to the employee at the desk opposite the cloakroom.
- RP80 detection accepts only VID:PID `0fe6:811e` and rejects IP-802 `353d:1249`/generic printer paths.
- A loopback-only signed canary backend issues only `TEST-VNVNC-*` non-redeemable codes for the future real 60-print RP80 soak; its HMAC/replay/idempotency/real-client transport tests pass.
- The exact six-row candidate policy is stored as `vnvnc-bot/deploy/artifact-kiosk-policy.proposed.json` with `approved:false`. Dry-run validation succeeds, while every apply path rejects it; changing only the boolean still fails because the reserved pending identity must be replaced by a real operator and timestamp.
- Canary awards are visibly marked `TEST` on every display and their RP80 receipt begins with `ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН`; the final rendered receipt still exact-decodes both QR payloads.
- The full official Telegram OIDC/PKCE URL remains server-side. ФОТОБУДКА ВИНОВНИЦЫ receives a 45-character opaque single-use pairing URL. EC-Q fits it in a v4 QR: 33 data modules plus the 4-module quiet zone on each side render at `123×123`, with `3×3` LED pixels per module and a 12-pixel quiet zone. Only 2/3 outer pixels remain, so the QR is effectively full-screen and exact-decodes from the final frame. `/k/{pairing_id}` validates TTL/session/attempt and redirects to the unchanged official Code+S256 flow.
- The main reel follows the VPISKA access-ticket language in VNVNC red/white: one 68 px winner, muted inset neighbor peeks with their prize names visible, an off-white grid chamber, ticket side notches, and a left-side white chevron pointing right.
- Every winning sector is deliberately typeset for its exact prize. The winner contains only the large prize name: no `VNVNC`, ID, barcode, mode, boost, Telegram or key legends, and no generic auto-shrink fallback.
- The drum is one circular 18-sector tape: three equal presentation-only appearances of each of the six prizes, freshly shuffled from immutable `award.id + coupon_code` for every spin. Equal prizes never touch, including the 18→1 seam. An idempotent server retry therefore replays the same order, while a new award gets a different order. No backend probability or stock is exposed by the visual duplicates.
- The committed spin runs for 10.8 seconds. It opens with a 3.6-second linear eight-sector excerpt at 450 ms/sector, then accelerates through at least 66 more sector crossings, performs two distinct false-lock/re-kick beats on non-winning sectors, overshoots by `0.14` sector and settles on the exact server-selected occurrence. Position remains an absolute function of elapsed time, so frame delta cannot change the result.
- Main-screen service labels are absent. KP4/KP6 still select auth/guest but are intentionally unlabeled. During Telegram pairing the ticker/LCD use text-free scan graphics; READY/ISSUING/SPINNING show the currently centered prize in sync with the reel; REVEAL/RESULT lock to the awarded prize. The ticker remains calibrated green at `safe_left=8`.
- All public device surfaces use the exact name `ФОТОБУДКА ВИНОВНИЦЫ`: main idle, LCD boot, HDMI/simulator caption, RP80 receipt, user prize message, admin notification and Telegram login hand-off. Internal compatibility identifiers such as `artifact.service`, environment variables and API routes are unchanged.

## Latest commands

```text
modular-arcade:
scripts/preflight-prize-drum-deployment.sh --focused
=> 93 passed; critical modules compile; both H.264/yuv420p preview videos
   contain no black interval; both compressed-video QR payloads decode exactly

vnvnc-bot:
PYTHONPATH=. /opt/homebrew/bin/pytest -q \
  tests/test_artifact_kiosk_user_delivery.py tests/test_artifact_kiosk.py \
  tests/test_prize_wheel.py tests/test_configure_artifact_kiosk_policy.py
=> 174 passed

broad photobooth suite:
=> 56 passed (2 pre-existing Pillow deprecation warnings)

complete modular-arcade suite:
PYTHONPATH=src /opt/homebrew/bin/pytest -q
=> 150 passed (the same 2 pre-existing Pillow deprecation warnings)
```

## Review artifacts

- `output/prize-drum-state-preview.png`
  - SHA-256 `134bf6d57d62285d49ba8f8d75fcfe6bc43b993876fd3677148e49affd44158d`
- `output/prize-drum-ticket-catalog.png`
  - all six deliberate large-type prize sectors and adjacent prize peeks
  - SHA-256 `89f12997aac7f3966f067e7114a3d10cb13606c3fee32489da56528a3b513661`
- `output/prize-drum-auth-oidc-frame.png`
  - full-screen `123×123` EC-Q v4 QR, exact-decoded short pairing URL
  - SHA-256 `8b7e9b02f50e1e955a97234df500962e67f65123eaa0b4beb0aa168b2535fd98`
- `output/prize-drum-motion-preview.mp4`
  - H.264, 768×768, yuv420p, 30fps, 15.30s
  - no black interval found by `blackdetect`
  - SHA-256 `732fc53fa12dc9a29984f6c4b2f6a314cc9fa347ec883e0a4fa2c38bd357e843`
- `output/prize-drum-walkthrough.mp4`
  - real main/ticker/LCD walkthrough: Telegram QR + scan pulse → ready → server-confirmed 10.8s circular spin with a slow random excerpt and two false locks → reveal → prize QR
  - H.264, 960×1200, yuv420p, 30fps, 18.17s; no black interval
  - auth and result QRs exact-decode from compressed video frames
  - SHA-256 `806a577709e8a7a896f3673d1791bfc0522d49155afa6e90de8fb405e4ea5608`
- `output/wheel-prize-roll-preview.png`
  - exact public name `ФОТОБУДКА ВИНОВНИЦЫ`
  - no leaked `START WHEEL` deep-link parameter in visible copy
  - exact-decoded QR payloads: `VNVNC-KSK-8F2M9Q` and `https://t.me/vnvncbattlebot?start=wheel`
  - SHA-256 `4fb1e1f460f86b21e4806d11818d75672e769ca4ce9c8be8f3b4f31f01774428`
- `output/prize-drum-canary-receipt.png`
  - prominent `ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН` banner
  - exact-decoded QR payloads: `TEST-VNVNC-000001` and `https://t.me/vnvncbattlebot?start=wheel`
  - SHA-256 `ec46639575288927279f754291ab67b383df09ac141c2152df8c4c2553d6bea5`

## Explicit remaining gates

1. Owner approves the visual/motion treatment.
2. Owner approves kiosk weights, nightly limits, total stock, merch wording, and shot quantity.
3. Owner accepts the ticker's calibrated green hardware exception; red remains unsafe on this cabinet.
4. Provision production device/OIDC secrets outside git and configure BotFather allowed URLs.
5. Supervised physical canary: LED auth QR, live boost, RP80 paper QRs, unplug/retry, staff scanner, bot/admin delivery, camera/display transitions, clean logs.
6. Run 50+ physical spin/print soak. Only then enable the feature flag and deploy.

No policy was seeded, no production feature flag was enabled, and no deployment was performed.
