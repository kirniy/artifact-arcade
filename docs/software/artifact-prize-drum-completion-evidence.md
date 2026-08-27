# ФОТОБУДКА ВИНОВНИЦЫ prize drum — completion evidence

Updated: 28 August 2026 (Europe/Moscow)

Overall verdict: **software/API/policy deployed and cabinet code synchronized;
the hidden mode remains fail-closed and disabled until the attended RP80 paper
canary and 60-print physical soak pass**.

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
- Receipt uses VNVNC Classic logo and exact regular-wheel QR. Merch directs the guest to the desk opposite the cloakroom; Friday drinks direct them to the bar in «Малая Виновница», Saturday drinks to «Ангар»; `TIX1FREE` prints its exact Fri/Sat validity; `TIX50` prints a large TicketsCloud text code and deliberately has no staff QR.
- RP80 detection accepts only VID:PID `0fe6:811e` and rejects IP-802 `353d:1249`/generic printer paths.
- A loopback-only signed canary backend cycles the exact eight-sector visual contract and issues only `TEST-VNVNC-*` non-redeemable codes for the real 60-print RP80 soak; its HMAC/replay/idempotency/real-client transport and `TIX50` no-staff-QR tests pass.
- The approved eight-row policy is stored in `vnvnc-bot/deploy/artifact-kiosk-policy.approved.json` and is applied in production: `SHOT1FREE 38`, `COCKTL 35`, `SHOTFR 15` (5/night), `TIX50 6` (1/night), `TIX1FREE 4` (4/night), `MERCHFREE 2` (1/night), with `DEP1K`/`DEP2K` inactive at weight zero and all total-stock fields unlimited.
- Canary awards are visibly marked `TEST` on every display and their RP80 receipt begins with `ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН`; the final rendered receipt still exact-decodes both QR payloads.
- The full official Telegram OIDC/PKCE URL remains server-side. ФОТОБУДКА ВИНОВНИЦЫ receives only an opaque single-use short pairing URL rendered as a full-screen, exact-decodable LED QR. `/k/{pairing_id}` validates TTL/session/attempt and redirects to the official Code+S256 flow; production OIDC credentials, callback and trusted origin are configured outside git and a real redirect smoke passed.
- The main reel follows the VPISKA access-ticket language in VNVNC red/white: one 68 px winner, muted inset neighbor peeks with their prize names visible, an off-white grid chamber, ticket side notches, and a left-side white chevron pointing right.
- Every winning sector is deliberately typeset for its exact prize. The winner contains only the large prize name: no `VNVNC`, ID, barcode, mode, boost, Telegram or key legends, and no generic auto-shrink fallback.
- The drum is one circular 24-sector tape: three equal presentation-only appearances of each of the eight visual sectors, freshly shuffled from immutable `award.id + coupon_code` for every spin. Equal prizes never touch, including the 24→1 seam. The two deposit sectors remain visible but are inactive and cannot be selected by production. An idempotent server retry therefore replays the same order, while a new award gets a different order. No backend probability or stock is exposed by the visual duplicates.
- The committed spin runs for 10.8 seconds. It opens with a 3.6-second linear eight-sector excerpt at 450 ms/sector, then accelerates through at least 66 more sector crossings, performs two distinct false-lock/re-kick beats on non-winning sectors, overshoots by `0.14` sector and settles on the exact server-selected occurrence. Position remains an absolute function of elapsed time, so frame delta cannot change the result.
- Main-screen service labels are absent. KP4/KP6 still select auth/guest but are intentionally unlabeled. During Telegram pairing the ticker/LCD use text-free scan graphics; READY/ISSUING/SPINNING show the currently centered prize in sync with the reel; REVEAL/RESULT lock to the awarded prize. The ticker remains calibrated green at `safe_left=8`.
- All public device surfaces use the exact name `ФОТОБУДКА ВИНОВНИЦЫ`: main idle, LCD boot, HDMI/simulator caption, RP80 receipt, user prize message, admin notification and Telegram login hand-off. Internal compatibility identifiers such as `artifact.service`, environment variables and API routes are unchanged.

## Latest commands

```text
modular-arcade:
scripts/preflight-prize-drum-deployment.sh
=> 214 passed (2 pre-existing Pillow deprecation warnings); critical modules
   compile; all three H.264/yuv420p preview videos are silent and contain no
   black interval; compressed auth/redeem QRs decode exactly and TIX50 has none

vnvnc-bot:
PYTHONPATH=. /opt/homebrew/bin/pytest -q \
  tests/test_artifact_kiosk.py tests/test_artifact_kiosk_user_delivery.py \
  tests/test_configure_artifact_kiosk_policy.py
=> 94 passed
```

## Review artifacts

- `output/prize-drum-state-preview.png`
  - SHA-256 `5d28a95bd4948f1d2acffff50b5593007e0d83ad39f898c86a0aa717e89db98e`
- `output/prize-drum-ticket-catalog.png`
  - all eight deliberate large-type visual sectors and adjacent prize peeks
  - SHA-256 `5e9c9baae73e015b5c5f0eecab60628e21e15cde6be1e3fd827ddfa8511fba98`
- `output/prize-drum-auth-oidc-frame.png`
  - full-screen `123×123` EC-Q v4 QR, exact-decoded short pairing URL
  - SHA-256 `8b7e9b02f50e1e955a97234df500962e67f65123eaa0b4beb0aa168b2535fd98`
- `output/prize-drum-motion-preview.mp4`
  - H.264, 768×768, yuv420p, 30fps, 15.30s
  - no black interval found by `blackdetect`
  - SHA-256 `fcba9a018cf820754a0bb80ec58fd7fc3d9d7be8bb81b9c9e0e459d1009d5543`
- `output/prize-drum-walkthrough.mp4`
  - real main/ticker/LCD walkthrough: Telegram QR + scan pulse → ready → server-confirmed 10.8s circular spin with a slow random excerpt and two false locks → reveal → prize QR
  - H.264, 960×1200, yuv420p, 30fps, 18.17s; no black interval
  - auth and result QRs exact-decode from compressed video frames
  - SHA-256 `2f93918f4ed1e4489b92637f147eaf838bad069a41ec618435d73ac1c1b89027`
- `output/wheel-prize-roll-preview.png`
  - exact public name `ФОТОБУДКА ВИНОВНИЦЫ`
  - no leaked `START WHEEL` deep-link parameter in visible copy
  - exact-decoded QR payloads: `VNVNC-KSK-8F2M9Q` and `https://t.me/vnvncbattlebot?start=wheel`
  - SHA-256 `68bf15aaa7dd693d25bd99ef0829606eee751d99eba62d53148c125f9a63fea0`
- `output/prize-drum-canary-receipt.png`
  - prominent `ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН` banner
  - exact-decoded QR payloads: `TEST-VNVNC-000001` and `https://t.me/vnvncbattlebot?start=wheel`
  - SHA-256 `3e1b4b8ec971be18b86f82d62c8be7d6ed5523d8deca43e3dd2f2eab06a597dc`

## Explicit remaining gates

1. Power the RP80 and run the supervised physical canary: paper QR/text-code matrix, unplug/retry, staff scanner, bot/admin delivery, camera/display transitions and clean logs.
2. Verify live Telegram accounts with 0/1/2+ boosts and decode the real LED auth QR at venue distance.
3. Run the 60-iteration physical spin/print soak. Only then enable the hidden-mode feature flag for guests.

The approved production policy and backend are deployed. The cabinet is synced,
but `ARTIFACT_PRIZE_DRUM_ENABLED=false`; no physical prize has been issued and no
production feature flag has been enabled.
