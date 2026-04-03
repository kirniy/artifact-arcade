# 2026-04-03 Cringe Party Photobooth Handoff

This note captures the Cringe Party photobooth work from April 3, 2026 and the safest way to deploy it once the ARTIFACT machine is online again.

## Scope

This document covers the changes requested in today’s session:

- new Cringe Party photobooth mode set
- updated idle visuals and ticker text
- local simulator and webcam validation
- S3 gallery listing fix
- safe deployment procedure for the Raspberry Pi machine

This is not a full dump of every modified file in the local worktree. The repo is currently dirty, so this note focuses on the changes from this session that are relevant to deployment and verification.

## Current Status

- Local repo: `/Users/kirniy/dev/modular-arcade`
- Branch: `main`
- Git state at time of writing: `main...origin/main [ahead 1]` plus additional uncommitted and untracked changes
- Important consequence: the Pi cannot receive today’s `modular-arcade` changes via `git pull` yet unless those local changes are committed and pushed first
- Website fix for `https://vnvnc.ru/gallery/photobooth` was already deployed separately from a clean worktree in `/Users/kirniy/dev/vnvnc-modern-photobooth-fix`

## What Changed In `modular-arcade`

### 1. New photobooth mode set

The single visible photobooth menu was reworked into three Cringe Party themed modes:

- `BRAINROT`
- `ЛЮБОВЬ И ГОЛУБИ`
- `WA ОТКРЫТКИ`

The main menu labels live in:

- `src/artifact/modes/manager.py`
- `src/artifact/telegram/remote.html`

The current selector descriptions under those modes are:

- `КРИНЖ ПАТИ`
- `ФАВТФАА ПЭПЭ`
- `ПЭПЭШНЕЙШЕ`

### 2. Theme generation behavior

Photobooth generation was changed so the three new modes behave as themed clones of the photobooth flow, with updated prompt rules:

- likeness preservation remains the top priority
- group photos must keep all people present
- the new outputs are centered around one main image instead of a grid layout
- the Cringe Party emblem is passed as an extra reference image
- extra unnecessary text was stripped out of the brainrot outputs
- the decorative title inside the generated art was normalized to `КРИНЖ ПАТИ`
- the wedding mode has a special rule: if the image contains multiple men and no women, they should be portrayed as wedding guests or friends, not as a couple

Key code paths:

- `src/artifact/ai/client.py`
- `src/artifact/ai/caricature.py`
- `src/artifact/modes/photobooth.py`
- `src/artifact/modes/photobooth_themes.py`

### 3. New Cringe Party assets

Added new theme/logo assets:

- `assets/images/brainrot.png`
- `assets/images/wedding.png`
- `assets/images/whatsapp.png`
- `assets/images/cringe-party-circle.png`

Added idle assets under:

- `assets/idle/`

The new idle material was intended to come from:

- `/Users/kirniy/dev/cringe-party/production/drafts`

and not from the broader `/Users/kirniy/dev/cringe-party/` tree.

### 4. Idle and selector text changes

Idle and selector copy was updated for the Cringe Party run:

- top ticker should say `LOLOLOLOLOLOL`
- no extra venue copy like `КОНЮШЕННАЯ 2В` in the mode selector ticker area
- no extra idle labels like `ПЛОЩАДКА`
- `VNVNC.RU` remains present where requested

Key code path:

- `src/artifact/animation/idle_scenes.py`

### 5. Local simulator and webcam work

The simulator was run locally on this Mac and the webcam path was debugged.

What was done:

- simulator startup was verified
- missing Python deps were installed into the local `.venv`
- camera enumeration on macOS was checked
- simulator camera open logic was hardened with explicit retries and warmup reads

Key code path:

- `src/artifact/simulator/mock_hardware/camera.py`

Local result:

- the simulator successfully opened the webcam on this Mac after the camera path fix
- at the time of validation, the active camera device was `iPhone Kirill Camera`

### 6. Gemini image model toggle

The image generation client now supports an env toggle for the active Gemini image model:

- `GEMINI_IMAGE_MODEL=gemini-3.1-flash-image-preview` for Nano Banana 2
- `GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview` for Nano Banana Pro
- `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image` for the older Nano Banana image model

Behavior:

- if the env var is missing, the code falls back to Pro for backward compatibility
- local repo defaults were updated to use Nano Banana 2 for now
- the live Pi should also keep the same env value so local and hardware behavior match

## What Changed For The Gallery

The public gallery problem was not an upload failure.

Root cause:

- the website page `https://vnvnc.ru/gallery/photobooth` was querying the Yandex gateway endpoint
- that endpoint was returning `403`
- the frontend collapsed that failure into an empty list, which is why the page showed `0 photos`

What was changed:

- `src/artifact/utils/s3_upload.py`
  - added public `manifest.json` publishing for `artifact/photobooth/`
  - photobooth uploads now refresh that manifest automatically
- `/Users/kirniy/dev/groktest/vnvnc-modern/src/services/selectelS3.ts`
  - added fallback to the S3-hosted manifest when the Yandex API fails or returns no photos

Important deployment nuance:

- the website fallback is already live
- the manifest was also published manually once during debugging
- however, the ARTIFACT machine still needs today’s `modular-arcade` update so future photobooth uploads automatically refresh `manifest.json`

During validation, the bucket contained `1001` photobooth images and the live website rendered `1001 фото`.

## Saved Test Outputs

Manual test outputs from today’s mode work were saved here:

- `/Users/kirniy/Downloads/modular-arcade-mode-tests-2026-04-03/`

That folder includes a `SUMMARY.txt` created during the testing pass.

## Known Follow-Ups

- Legacy assets are still present in the repo, including `assets/images/malchishnik.png`
- The active 3-mode menu no longer uses that theme, but if old bachelor-party imagery still appears on the machine after deployment, treat it as a stale-asset or stale-runtime-state problem and re-check the running code and service restart state
- The Yandex listing endpoint still returns `403`; the site now survives because of the new manifest fallback, but the server-side endpoint itself is not fixed yet
- The local worktree contains unrelated or at least undocumented modifications beyond the files explicitly listed in this note; inspect before committing anything broad

## Safe Deployment Plan Once The Machine Is Online

### 1. Verify the machine is reachable

Prefer Tailscale first:

```bash
tailscale status | rg artifact
ssh kirniy@artifact.tailb30214.ts.net
```

Fallbacks that already exist in project docs and scripts:

```bash
ssh kirniy@100.115.122.91
ssh kirniy@artifact.local
```

### 2. Take a machine snapshot before touching anything

From this Mac, in the local repo:

```bash
cd /Users/kirniy/dev/modular-arcade
ARTIFACT_HOST=kirniy@artifact.tailb30214.ts.net ./scripts/snapshot_artifact_machine.sh
```

If Tailscale DNS is not resolving yet, use the Pi IP instead:

```bash
ARTIFACT_HOST=kirniy@100.115.122.91 ./scripts/snapshot_artifact_machine.sh
```

This gives you a rollback artifact under `machine-backups/`.

### 3. Inspect the Pi worktree before pulling

On the Pi:

```bash
cd ~/modular-arcade
git status -sb
git fetch origin main
git log --oneline --decorate --max-count=5
```

Stop here if the Pi has unexpected local changes. Do not blindly `git pull` over an unknown dirty worktree.

### 4. Make sure today’s local work is actually on `origin/main`

This is the critical gate.

At the time this note was written, the local Mac repo still had:

- one local commit ahead of `origin/main`
- additional unstaged and untracked work

That means a Pi-side `git pull origin main` will not bring over all of today’s work yet.

Safe options:

- commit and push the wanted `modular-arcade` changes from this Mac first, then deploy on the Pi with `git pull`
- if an emergency deploy is needed before commit/push, copy the exact intended files deliberately instead of using a blind whole-tree sync

Preferred path:

```bash
# On this Mac, after reviewing the dirty worktree carefully
git add <only the intended files>
git commit -m "..."
git push origin main
```

Then on the Pi:

```bash
cd ~/modular-arcade
git pull origin main
```

### 5. Restart services manually

Once the correct code is on the Pi:

```bash
sudo systemctl restart artifact
sudo systemctl restart arcade-bot
systemctl status artifact arcade-bot --no-pager
journalctl -u artifact -n 200 --no-pager
```

The repo already contains `scripts/autopull.sh`, but do not rely on autopull for today’s session until the intended commits are actually pushed.

## Post-Deploy Verification Checklist

After restart, verify all of the following on the actual machine:

- the mode selector shows exactly three photobooth modes:
  - `BRAINROT`
  - `ЛЮБОВЬ И ГОЛУБИ`
  - `WA ОТКРЫТКИ`
- the selector copy under them is:
  - `КРИНЖ ПАТИ`
  - `ФАВТФАА ПЭПЭ`
  - `ПЭПЭШНЕЙШЕ`
- the top ticker reads `LOLOLOLOLOLOL`
- no stray `КОНЮШЕННАЯ 2В` appears in the selector ticker area
- no stray idle labels like `ПЛОЩАДКА` appear
- the webcam feed is live
- each mode can complete a real capture
- a fresh photobooth upload lands in Selectel S3
- `artifact/photobooth/manifest.json` updates after that upload
- `https://vnvnc.ru/gallery/photobooth` still lists photos and eventually reflects the new upload

## Key Files From This Session

Inside `modular-arcade`:

- `src/artifact/ai/client.py`
- `src/artifact/ai/caricature.py`
- `src/artifact/modes/photobooth.py`
- `src/artifact/modes/photobooth_themes.py`
- `src/artifact/modes/manager.py`
- `src/artifact/animation/idle_scenes.py`
- `src/artifact/simulator/mock_hardware/camera.py`
- `src/artifact/utils/s3_upload.py`
- `src/artifact/telegram/remote.html`
- `assets/images/brainrot.png`
- `assets/images/wedding.png`
- `assets/images/whatsapp.png`
- `assets/images/cringe-party-circle.png`
- `assets/idle/`

Outside `modular-arcade`:

- `/Users/kirniy/dev/groktest/vnvnc-modern/src/services/selectelS3.ts`

## Bottom Line

The machine-side deployment is not blocked by missing instructions. It is blocked only by source-of-truth hygiene:

- decide which local `modular-arcade` changes are the intended deploy set
- commit and push them cleanly
- snapshot the machine before rollout
- pull on the Pi
- restart `artifact` and `arcade-bot`
- verify the three modes, webcam, and gallery manifest refresh
