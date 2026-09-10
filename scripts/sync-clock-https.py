#!/usr/bin/env python3
"""Repair large clock drift when the venue network cannot reach UDP NTP.

Keep normal NTP enabled. Require two independently hosted, TLS-verified HTTP
Date headers to agree before stepping the clock. Never disable TLS validation.
"""

import logging
import subprocess
import time
import urllib.error
import urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime


SOURCES = (
    "https://s3.ru-7.storage.selcloud.ru/",
    "https://www.google.com/generate_204",
    "https://www.cloudflare.com/",
)


def sample_time(url):
    started = time.monotonic()
    request = urllib.request.Request(
        url, method="HEAD", headers={"Cache-Control": "no-cache"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=8)
    except urllib.error.HTTPError as exc:
        # An unsigned S3 HEAD may return 403; its TLS-verified Date is usable.
        response = exc
    with response:
        date_header = response.headers.get("Date")
        age = float(response.headers.get("Age", "0"))
    finished = time.monotonic()
    if not date_header or age != 0 or finished - started > 10:
        raise ValueError("Missing, cached, or slow server time")
    server_time = parsedate_to_datetime(date_header)
    if server_time.tzinfo is None or server_time.utcoffset().total_seconds() != 0:
        raise ValueError("Server time must be UTC")
    return server_time.astimezone(timezone.utc).timestamp() + (finished - started) / 2, finished


def agreed_time(samples, now):
    adjusted = [epoch + now - observed for epoch, observed in samples]
    for index, left in enumerate(adjusted):
        for right in adjusted[index + 1:]:
            if abs(left - right) <= 10:
                return (left + right) / 2
    raise ValueError("Two independent HTTPS clocks did not agree")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    samples = []
    for url in SOURCES:
        try:
            samples.append(sample_time(url))
        except Exception as exc:
            logging.warning("Clock source %s unavailable: %s", url, exc)
    target = agreed_time(samples, time.monotonic())
    offset = target - time.time()
    if abs(offset) <= 30:
        logging.info("HTTPS clock check passed; offset %.1fs", offset)
        return
    subprocess.run(["/usr/bin/date", "-u", "-s", f"@{target:.3f}"], check=True)
    logging.info("Corrected system clock by %.1fs using agreeing HTTPS sources", offset)


if __name__ == "__main__":
    main()
