"""Typed access to editable application settings (thresholds, SLAs, demo toggles)."""
from sqlalchemy.orm import Session

from ..models import ApplicationSetting

DEFAULTS: dict[str, tuple[object, str]] = {
    "duplicate.likely_threshold": (85, "Score at or above which a match is a likely duplicate (blocks without justification)."),
    "duplicate.review_threshold": (70, "Score at or above which a match needs human review."),
    "sla.escalate_after_overdue_days": (1, "Working days past the due date before a task escalates."),
    "sla.total_turnaround_target_days": (5, "Target end-to-end turnaround (submission to SAP creation), working days."),
    "sap.mock_fail_next": (0, "Demo only: number of upcoming mock SAP calls that should fail."),
    "analytics.window_start": ("2025-10", "First month of the stated analysis window (synthetic data)."),
    "analytics.window_end": ("2026-09", "Last month of the stated analysis window (synthetic data)."),
    "forecast.rolling_window": (6, "Months used by the rolling-average baseline (the brief's current approach)."),
}


def get(db: Session, key: str):
    row = db.get(ApplicationSetting, key)
    if row is None:
        return DEFAULTS[key][0]
    return row.value


def set_value(db: Session, key: str, value, user_id: int | None = None) -> ApplicationSetting:
    row = db.get(ApplicationSetting, key)
    if row is None:
        row = ApplicationSetting(key=key, value=value, description=DEFAULTS.get(key, (None, ""))[1])
        db.add(row)
    row.value = value
    row.updated_by_id = user_id
    db.flush()
    return row


def ensure_defaults(db: Session) -> None:
    for key, (value, desc) in DEFAULTS.items():
        if db.get(ApplicationSetting, key) is None:
            db.add(ApplicationSetting(key=key, value=value, description=desc))
    db.flush()
