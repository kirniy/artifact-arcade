# 2026-06-30 Cringe Party Restore

Intent:

- Restore the Cringe Party photobooth set as the default active booth experience.
- Keep the TV wall off.
- Use Vertex for image generation.
- Use Nano Banana 2 Lite: `GEMINI_IMAGE_MODEL=gemini-3.1-flash-lite-image`.

Active photobooth menu:

- `BRAINROT`
- `ЛЮБОВЬ И ГОЛУБИ`
- `WA ОТКРЫТКИ`

Activation:

```bash
cd /home/kirniy/modular-arcade
ARTIFACT_REMOTE_DIR=/home/kirniy/modular-arcade ./scripts/activate-cringe-party-photobooth.sh --restart
```

The activation script writes:

```bash
PHOTOBOOTH_THEME=brainrot
PHOTOBOOTH_MENU_MODES=brainrot,wedding,whatsapp
PHOTOBOOTH_CAMERA_SELECTOR_ENABLED=false
PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=false
PHOTOBOOTH_PRINT_FORTUNES=false
ARTIFACT_IMAGE_PROVIDER=vertex
ARTIFACT_GEMINI_PROVIDER=vertex
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=gen-lang-client-0412477988
GOOGLE_CLOUD_LOCATION=global
GEMINI_IMAGE_MODEL=gemini-3.1-flash-lite-image
```

Autopull:

- `scripts/autopull.sh` auto-applies this activation when the Pi comes online.
- It then uses `scripts/restart-artifact-if-idle.sh`, so the booth restarts only when idle.
- Disable this one-off restore by setting `ARTIFACT_AUTO_ACTIVATE_CRINGE_PARTY=0`.

Verification after the Pi is online:

```bash
cd /home/kirniy/modular-arcade
grep -E 'PHOTOBOOTH_THEME|PHOTOBOOTH_MENU_MODES|GEMINI_IMAGE_MODEL|ARTIFACT_IMAGE_PROVIDER|GOOGLE_GENAI_USE_VERTEXAI' .env
systemctl status artifact arcade-bot artifact-upload-spool --no-pager
journalctl -u artifact -n 120 --no-pager
```
