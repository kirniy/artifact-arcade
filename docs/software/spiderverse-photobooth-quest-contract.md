# SPIDERVERSE photobooth quest contract

## Kiosk behavior

- Feature flag: `ARTIFACT_SPIDERVERSE_QUEST_ENABLED=true`.
- Enter or leave the hidden quest profile by holding physical numpad `7` for 2 seconds.
- Existing prize drum remains unchanged on physical numpad `9`.
- A short press of `7` is still forwarded as an ordinary keypad digit.
- The quest attract screen says `ПАУЧЬЕ ЧУТЬЁ` and `КВЕСТ · КОКТЕЙЛЬ + ШОТ`.
- The large red button starts the existing `spiderverse` photobooth countdown and generation.
- Each successful generation queues the normal photobooth photo receipt first, followed by the dedicated quest receipt.

## Telegram contract

The kiosk has no quest-session API and no network dependency beyond the normal photo pipeline.
Every quest receipt contains the same exact deep link:

`https://t.me/vnvncbattlebot?start=spiderquest`

The bot backend owns all eligibility and idempotency. It must identify the Telegram user after `/start spiderquest`, derive the current Moscow club night, and allow at most one completion/reward for that `(telegram_user_id, club_night)` pair. Re-scanning the same or another receipt must return the existing state instead of granting another reward.

The printed QR encodes only the canonical URL above. It contains no kiosk-generated identity, prize, token, or authorization material.

## Failure boundaries

- A bot/backend outage cannot block the camera, AI generation, normal photo receipt, or quest receipt.
- The quest receipt remains a valid entry point and can be scanned again when Telegram/backend service recovers.
- The physical QR is rendered at over 300 px with high error correction and a Telegram center mark; the automated test decodes it back to the exact canonical URL.
