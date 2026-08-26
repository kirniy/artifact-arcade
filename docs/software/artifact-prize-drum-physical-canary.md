# ФОТОБУДКА ВИНОВНИЦЫ prize drum — supervised physical canary

Status: **prepared, not authorized, not run**.

This runbook may be executed only after:

- operator approves weights, nightly limits, total stock, merch wording and shot quantity;
- visual/motion and the calibrated green ticker exception are accepted;
- shared OIDC invalidation and strict admin-delivery hardening are approved and tested;
- ФОТОБУДКА ВИНОВНИЦЫ, RP80 paper and a staff scanner are physically attended.

Never print environment values or secrets into the terminal transcript. Never use the production backend for the 50+ mechanical soak; use a separately signed staging/canary endpoint whose coupons are visibly non-redeemable.

## 1. Preflight with feature disabled

Run the fail-closed repository gate first. It compiles critical modules, runs
the full test suite, regenerates both videos, rejects black intervals, decodes
both compressed-video QRs, then checks the exact RP80 USB identity, camera,
services, non-mock production configuration, API reachability and recent logs:

```bash
cd ~/modular-arcade
scripts/preflight-prize-drum-deployment.sh --hardware
```

It does not enable the mode or print. Any failed check blocks activation.

Record:

```text
date/time (MSK):
operator:
ФОТОБУДКА ВИНОВНИЦЫ git revision:
VNVNC backend revision/deployment:
rollback revision:
RP80 paper roll loaded:
staff scanner account:
test Telegram accounts with 0 / 1 / 2+ boosts:
```

Read-only cabinet checks:

```bash
systemctl is-active artifact artifact-dashboard tailscaled
lsusb | grep -i '0fe6:811e'
rpicam-hello --list-cameras
journalctl -u artifact --since '15 minutes ago' --no-pager | tail -200
```

Expected:

- `artifact.service` healthy before any switch;
- RP80 exists as VID:PID `0fe6:811e`;
- IP-802 may coexist as `353d:1249`, but must never receive the prize receipt;
- camera IMX708 is listed;
- no restart loop, traceback, DRM/HDMI black-frame error or printer mock message.

Configuration checks must report presence/boolean only:

- `ARTIFACT_ENV=hardware`;
- `ARTIFACT_PRIZE_DRUM_ENABLED` remains off until step 3;
- `ARTIFACT_KIOSK_STUB` is unset/false;
- `ARTIFACT_MOCK_PRINTER` and `ARTIFACT_MOCK_HARDWARE` are unset/false;
- HTTPS canary/production API URL is configured;
- device ID and a non-placeholder HMAC secret are present;
- Telegram OIDC client ID/secret/callback are present only on backend;
- BotFather allowed URL equals the deployed HTTPS callback origin/path.

## 2. Staging hardware pass — no redeemable prizes

Use the real cabinet, displays, keypad, audio and RP80, but a separately signed canary backend. Every printed ticket must say `ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН`; it must not create a production `Spin`, `Coupon`, admin alert or user chest item.

The repository includes a signed loopback-only implementation:

```bash
cd ~/modular-arcade
sudo -E ARTIFACT_ENV=hardware PYTHONPATH=src \
  .venv/bin/python scripts/run_prize_drum_canary_backend.py --host 127.0.0.1 --port 8765
```

It refuses non-loopback binding, requires the configured device ID/HMAC secret without printing either value, rejects stale/replayed signatures, cycles all six sectors, and issues only `TEST-VNVNC-*` codes with the terms `ТЕСТОВЫЙ ЧЕК — НЕ ДЕЙСТВИТЕЛЕН`. Point the supervised ФОТОБУДКА ВИНОВНИЦЫ process to `http://127.0.0.1:8765`; localhost HTTP is accepted only for this same-machine path. Keep `ARTIFACT_KIOSK_STUB=false` so the real signed HTTP client and real RP80 path are exercised.

Exercise:

1. From idle, short `9` still behaves as an ordinary digit and does not enter hidden mode.
2. Hold `9` for 1.99 s: no toggle.
3. Release, then hold `9` for 2.00 s: exactly one toggle; no camera capture.
4. Hold without release for another 3 s: no second toggle.
5. Press `6`: persistent guest flow; one staging spin.
6. Press `4`: persistent Telegram flow; fresh OIDC QR.
7. Scan OIDC QR from the 3 mm LED panel at normal guest distance.
8. Run accounts with 0, 1 and 2+ boosts; verify `1`, `2`, `3` total spins.
9. Disconnect network after server commit but before response; retry must return the same issue/code.
10. Unplug RP80 before printing: award QR remains visible and UI says `ПЕЧАТЬ НЕ ГОТОВА`.
11. Reconnect RP80 and press the main button: exactly the same issue prints once; no re-spin.
12. Request exit during issue/spin/reveal/print: exit waits for a safe boundary.
13. Return to the ordinary photobooth; camera preview and main screen must recover without black frames.

## 3. Owner-approved production canary

Apply the signed policy manifest first in dry-run mode. Verify the diff contains exactly six `ARTIFACT_KIOSK` rows and no ordinary `Prize` mutation. Production apply requires all three controls:

```text
manifest operator_approval.approved = true
--apply
--confirm-production-policy
```

Enable the feature for one attended guest at a time. For each canary, compare the same immutable issue across:

- main-screen result;
- RP80 receipt;
- raw QR payload and printed code;
- existing VNVNC chest;
- personal bot message;
- admin message;
- staff scanner validation/redemption audit.

Required real cases:

- guest ordinary prize;
- authenticated ordinary prize with no boost;
- one boost and one bonus spin;
- 2+ boosts and two bonus spins;
- `TIX1FREE` showing the next complete Friday/Saturday pair;
- two simultaneous staff redeem attempts: one success, one `ALREADY_REDEEMED`;
- boundary verification at 06:59:59 and 07:00:00 on a controlled clock/staging record.

Both paper QRs must scan from the actual RP80 roll:

1. primary QR decodes to the exact uppercase coupon code;
2. secondary QR decodes exactly to `https://t.me/vnvncbattlebot?start=wheel`.

## 4. Fifty-plus physical spin/print soak

Return to the non-redeemable canary backend. Run at least 60 iterations to provide margin over the 50 requirement. Record per iteration:

```text
iteration, session_id, request_id, issue_id, coupon_code,
server prize, landed sector, PRINT_COMPLETE/PRINT_ERROR,
paper QR1 decode, paper QR2 decode, ticker fit, main-screen health
```

Pass conditions:

- 60 unique intentional issues and coupon codes;
- each retried request ID maps to exactly one issue;
- exactly 60 `PRINT_COMPLETE`, zero silent/mocked success;
- no RP80 job reaches IP-802;
- zero clipped ticker strings; no lit pixels left of physical `x=8`;
- no main-screen black interval or camera-loss regression;
- all reel landings equal the server prize;
- no duplicate personal/admin message for the same issue;
- no critical/error traceback or service restart;
- thermal output remains readable at the end of the roll/soak.

## 5. Log capture and rollback

Capture bounded logs without secrets:

```bash
journalctl -u artifact --since 'CANARY_START_TIME' --no-pager > /tmp/artifact-prize-drum-canary.log
systemctl is-active artifact
```

After the supervised switch, run the same gate against the enabled service:

```bash
cd ~/modular-arcade
scripts/preflight-prize-drum-deployment.sh --post-activation
```

Immediately disable the feature and restore the previous known-good service revision if any of these occur:

- duplicate award/code/redemption;
- printer mock success or IP-802 misrouting;
- OIDC identity visible to the next guest;
- black main screen/camera failure;
- clipped/deformed ticker;
- result disagreement between display, receipt, bot, admin or scanner;
- backend ordinary-wheel cooldown/stock/limits change;
- repeated critical log or service restart.

Rollback does not delete issued prizes. Already committed coupons remain valid/auditable and must be handled through the normal scanner flow.

## 6. Sign-off

- [ ] policy values/wording approved and applied
- [ ] real LED OIDC QR decoded
- [ ] live boost counts 0/1/2+ verified
- [ ] real RP80 primary QR decoded
- [ ] real RP80 secondary QR decoded
- [ ] unplug/reconnect/retry passed
- [ ] guest and authenticated chest/bot/admin flows agree
- [ ] staff concurrent redemption passed
- [ ] camera/display/ticker passed
- [ ] 60-iteration physical soak passed
- [ ] recent logs clean
- [ ] rollback tested
- [ ] owner authorizes production enablement
