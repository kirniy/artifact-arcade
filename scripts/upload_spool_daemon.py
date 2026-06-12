#!/usr/bin/env python3
"""Drain ARTIFACT upload spool outside the display/camera service."""

from __future__ import annotations

import logging
import os
import signal
import time

from artifact.utils.s3_upload import retry_pending_uploads


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("artifact.upload_spool_daemon")
    interval_seconds = int(os.getenv("ARTIFACT_UPLOAD_RETRY_INTERVAL", "30"))
    batch_limit = int(os.getenv("ARTIFACT_UPLOAD_RETRY_LIMIT", "100"))
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("Upload spool daemon started: interval=%ss limit=%s", interval_seconds, batch_limit)

    while running:
        try:
            summary = retry_pending_uploads(limit=batch_limit)
            if summary["retried"] or summary["failed"]:
                logger.info("Pending upload retry pass: %s", summary)
        except Exception:
            logger.exception("Pending upload retry pass crashed")

        for _ in range(interval_seconds):
            if not running:
                break
            time.sleep(1)

    logger.info("Upload spool daemon stopped")


if __name__ == "__main__":
    main()
