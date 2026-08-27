# VNVNC PHOTOBOOTH runtime updates

The production Raspberry Pi uses a machine-local `artifact-runtime` branch.
Its only intentional difference from `origin/main` is the removal of archival,
non-runtime media that is not needed on the booth SD card.

`scripts/autopull.sh` fetches `origin/main` every five minutes and merges it
into that branch. The updater:

- treats `origin/main` as the canonical source for deployed code;
- keeps the Pi's committed media footprint during merges;
- refuses to overwrite unexpected tracked edits;
- refuses to overwrite a colliding untracked path;
- aborts a failed merge back to the exact pre-merge checkpoint;
- restarts `artifact.service` only through the idle-gated restart helper.

Operational checks:

```bash
systemctl status arcade-autopull.timer
systemctl status arcade-autopull.service
journalctl -u arcade-autopull.service -n 100 --no-pager
cd /home/kirniy/modular-arcade
git branch --show-current
git status --short
git merge-base --is-ancestor origin/main HEAD
```

The last command must exit successfully. Untracked runtime data is allowed;
tracked code must remain clean.
