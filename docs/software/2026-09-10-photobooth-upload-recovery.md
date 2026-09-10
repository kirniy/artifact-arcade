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

## Live recovery still required

Tailscale is running and the existing node identity was preserved. SSH to the
machine requires an interactive identity check. The existing Frankfurt recovery
tunnel on port 22091 is not listening. No machine restart, queue modification,
or photo recovery has been performed in this session.

After access is restored:

1. Inspect live revision, `artifact-upload-spool` status and logs, pending jobs,
   free disk space, and the original September 7 upload errors. Preserve photos.
2. Deploy the tested source through the normal idle-gated update path. Verify
   all affected services loaded it, without changing themes or Vertex settings.
3. Retry existing jobs under their original object keys, beginning with the
   reported photo. Confirm S3 object content type and byte length, rather than
   trusting a public website HTTP 200.
4. Refresh the manifest and compare all upload event keys after the last known
   good photo against a complete S3 listing. Recover missing payloads from the
   machine's generated-image logs only if a spool payload is absent.
5. Verify the target short URL and gallery in the browser before reporting the
   incident resolved.
