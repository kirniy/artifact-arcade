"""Date-based Project X weekend; independent of uptime and host timezone."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo('Europe/Moscow')
START = datetime(2026, 9, 18, 7, tzinfo=MOSCOW)
END = datetime(2026, 9, 20, 7, tzinfo=MOSCOW)


def scheduled_theme(now=None):
    if os.getenv('ARTIFACT_CLUB_THEME_SCHEDULE', '').lower() != 'project-x-2026':
        return None
    now = datetime.now(MOSCOW) if now is None else now
    if now.tzinfo is None:
        raise ValueError('Schedule requires a timezone-aware clock')
    return 'project-x' if START <= now.astimezone(MOSCOW) < END else 'vse-svoi'
