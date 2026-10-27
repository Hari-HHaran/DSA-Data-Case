"""Time helpers: UTC-naive storage, country-local working-day SLA arithmetic."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def add_working_days(start_utc: datetime, days: float, tz_name: str = "Asia/Singapore") -> datetime:
    """Adds (or, if negative, subtracts) working days (Mon–Fri) in the given local time zone.
    Public holidays are not modelled."""
    tz = ZoneInfo(tz_name)
    local = start_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    step = 1 if days >= 0 else -1
    whole = int(abs(days))
    frac = abs(days) - whole
    if step > 0:
        # A request arriving at the weekend starts its clock on Monday morning.
        while local.weekday() >= 5:
            local = (local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    moved = 0
    while moved < whole:
        local += timedelta(days=step)
        if local.weekday() < 5:
            moved += 1
    if frac:
        local += timedelta(hours=24 * frac * step)
        while local.weekday() >= 5:
            local += timedelta(days=step)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def working_days_between(start: datetime, end: datetime) -> float:
    """Approximate elapsed working days between two UTC timestamps (weekends excluded)."""
    if end <= start:
        return 0.0
    total = 0.0
    cur = start
    while cur < end:
        nxt = min(end, (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
        if cur.weekday() < 5:
            total += (nxt - cur).total_seconds() / 86400
        cur = nxt
    return round(total, 2)
