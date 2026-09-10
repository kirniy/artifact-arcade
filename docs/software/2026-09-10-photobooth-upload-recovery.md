# Photobooth upload recovery, September 10, 2026

## Confirmed findings

Read the Codex threads `019f70db-768b-7ee2-a226-2e2a88108878`
(Add ЖАРА photobooth theme) and `01a0720b-37a7-7822-88cf-cc2f567e2101`
(Audit project stability), including their September 5 gallery repairs.

The live gallery API still uses the repaired paginated S3 listing. It reports
5,374 photos and returns the newest 5,000. Its newest key is
`artifact/photobooth/photobooth_20260907_051107_5339f7ad.png`.
The public manifest agrees and was last updated at `2026-09-07T02:11:44Z`.
A separate listing restricted to September 7 returns 28 photos, with the same
newest key.

The reported `photobooth_20260907_111108_3f937355.png` is absent from both
listings. Its public URL returns HTML, not a PNG. HTTP 200 alone is insufficient
to establish that a photo exists because the storage website serves HTML for
missing paths.

The uploader returned `success=True` for a reserved URL after an unsuccessful
upload. Photobooth then emitted a success event and the bot announced
“Новое фото готово”. This is a confirmed status bug; the actual machine-side
transport failure and backlog remain unverified pending SSH access.

## Changes and validation

- Queued results explicitly carry `success=False, queued=True`, preserving QR
  information for the photobooth but never claiming the object was uploaded.
- Only an existing payload and metadata file qualify as a durable queued job.
- The bot labels queued photos as waiting for upload and excludes them from
  completed-failure statistics. The spool emits the ready event after success.
- AWS CLI timeouts and missing executable errors now reach direct HTTPS upload.
- 20 targeted tests pass, including failed upload persistence, timeout fallback,
  missing-payload handling, notification state, successful retry, manifest
  pagination, face gating, and ticker behavior.

## Live recovery completed

SSH access was restored. The machine clock was three days behind, while
systemd-timesyncd timed out against every configured UDP NTP server. Both AWS
CLI and direct S3 requests failed with `RequestTimeTooSkewed`. Correcting the
clock immediately allowed the running spool daemon to upload all three pending
photos (a third photo had joined the queue during diagnosis):

- `photobooth_20260907_104420_87acf73d.png` — 1,288,040 bytes
- `photobooth_20260907_111108_3f937355.png` — 1,088,596 bytes
- `photobooth_20260907_112710_eb27f38f.png`

The queue is empty. A complete signed S3 listing contains all 436 distinct photo
keys recorded in machine events since August 27; missing count is zero. The
reported short link was verified in a browser and opens the 768×1376 PNG.

The uploader/status fix and clock safeguard were merged into the runtime branch.
The machine-local AI client patch was preserved (its diff hash is unchanged).
All three application services were restarted while idle and are active.

`artifact-clock-sync.timer` is enabled and active, checking at boot and every
five minutes. It requires two independently hosted TLS-verified HTTP Date
headers to agree before correcting drift over 30 seconds; NTP remains enabled.
The live service completed successfully with a 1.1-second offset. Its script is
installed root-owned at `/usr/local/libexec/artifact-clock-sync.py`, with source
in `scripts/sync-clock-https.py`. For future updates, install that source to the
system path as well as updating the unit files.

Clock corrections preserve existing photo filenames and short links; timestamps
embedded in photos taken while the clock was wrong are not rewritten.
