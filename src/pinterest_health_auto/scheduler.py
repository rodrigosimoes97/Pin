from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import settings


class PinScheduler:
    us_prime_hours = [8, 12, 18, 20, 21]

    def schedule_batch(self, count: int, start: datetime | None = None) -> list[datetime]:
        tz = ZoneInfo(settings.timezone)
        now = (start or datetime.now(tz)).astimezone(tz)
        count = min(count, settings.daily_pin_limit)
        day_anchor = now.replace(minute=0, second=0, microsecond=0)
        slots: list[datetime] = []

        for idx in range(count):
            hour = self.us_prime_hours[idx % len(self.us_prime_hours)]
            candidate = day_anchor.replace(hour=hour)
            if candidate <= now:
                candidate += timedelta(days=1)
            jitter = random.randint(5, 50)
            slots.append(candidate + timedelta(minutes=jitter))
        slots.sort()
        return slots
