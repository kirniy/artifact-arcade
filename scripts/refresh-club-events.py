#!/usr/bin/env python3
"""Refresh the same durable event cache used by the booth; no theme/guest mutation."""
import os
from pathlib import Path
from dotenv import dotenv_values
from artifact.modes.ticketscloud_theme_schedule import EventFeed

root = Path(__file__).resolve().parents[1]
for key, value in dotenv_values(root / ".env").items():
    if value is not None:
        os.environ[key] = value
feed = EventFeed()
if not feed.refresh():
    raise SystemExit("Tickets Cloud schedule refresh failed; existing cache preserved")
print(f"Verified Tickets Cloud cache: {len(feed.snapshot())} SPb events")
