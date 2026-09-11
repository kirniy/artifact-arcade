# September 12 photobooth upload audit

The 00:26:08 error concerned `photobooth_20260912_002549_9650a749.png`.
The spool daemon uploaded it and removed the local payload at 00:26:00. The
foreground AWS request failed eight seconds later; direct fallback then could
not read the removed file. The September 10 missing-payload check reported a
failure despite successful background delivery.

Inspected 12,334 service log lines since September 11 00:00. Seven distinct
missing-payload errors matched seven publicly accessible PNG files. A complete
signed S3 listing matched all 29 recorded photo keys since September 11; none
were missing. The reported image has the expected 1,063,511 bytes.

Fix: foreground upload and daemon retry now share stable, striped filesystem
locks. Foreground ownership starts before publishing the job, and continues
through fallback, result handling and cleanup. The daemon skips owned jobs and
rechecks metadata under the lock. Lock files remain in place to avoid inode
replacement races; kernel ownership is released on process exit/crash.

Verification: 21 upload/manifest/clock tests passed locally. The targeted
upload/manifest/Tropical Thai integration selection passed 19 tests (activation
excluded because this checkout has unrelated in-progress theme assets). An
actual separate-process Linux lock check and compilation passed on the Pi.
Pi pytest is not installed; no claim is made that pytest ran there.

Also updated Tropical Thai's prompt and style argument to require every guest,
including face, hair, body and clothing, to be a stylized Octane-like 3D cartoon
character. Individual likeness, original clothing and the event emblem remain
required. No new generated image was used to judge the visual result.

Deployed as runtime merge 4606c21. The only add/add merge conflict was the theme
prompt; resolved to the reviewed requested prompt. The existing machine-local
AI client edit was preserved. Artifact, bot and spool services restarted while
idle at 00:32:08–00:32:09 and are active.

Remaining observations: intermittent transport failures recover through retries;
clock fallback had two failed consensus checks but subsequent checks succeeded.
The current USB inventory contains no printer and `/dev/usb/lp*` is absent.
The application reports a mock printer, so physical printing cannot be certified.
A warning also refers to an absent, unused legacy SAGA video; the selected
Tropical Thai idle video loads successfully. These warnings were not hidden.
