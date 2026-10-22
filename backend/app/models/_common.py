from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def created_at_col():
    return mapped_column(DateTime, default=utcnow, nullable=False)


def updated_at_col():
    return mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
