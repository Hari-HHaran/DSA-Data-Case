"""Notification service. In-app notifications are real; Teams/Outlook are a mock outbox.

Mock-channel messages are stored with delivery_status=MOCK_QUEUED and are never sent anywhere.
A future Microsoft Graph adapter would replace `MockM365Adapter.dispatch`.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import NotificationEvent, Role, User
from .clock import utcnow

# Which mock external channels each event type would use in production.
EXTERNAL_CHANNELS = {
    "APPROVAL_ASSIGNED": ["MOCK_TEAMS", "MOCK_OUTLOOK"],
    "SLA_REMINDER": ["MOCK_TEAMS"],
    "ESCALATION": ["MOCK_TEAMS", "MOCK_OUTLOOK"],
    "RETURNED_FOR_CHANGES": ["MOCK_OUTLOOK"],
    "REQUEST_REJECTED": ["MOCK_OUTLOOK"],
    "SAP_CREATED": ["MOCK_TEAMS", "MOCK_OUTLOOK"],
    "SAP_FAILED": ["MOCK_TEAMS"],
    "MDM_VERIFICATION_READY": ["MOCK_TEAMS"],
    "FOLLOWUP_ASSIGNED": ["MOCK_TEAMS"],
}


class MockM365Adapter:
    mode = "mock"

    def dispatch(self, channel: str, recipient: User, title: str, body: str) -> str:
        # Intentionally does not send. Returns the status stored against the outbox entry.
        return "MOCK_QUEUED"


adapter = MockM365Adapter()


def users_with_role(db: Session, role_code: str) -> list[User]:
    return list(
        db.execute(select(User).join(User.roles).where(Role.code == role_code, User.is_active.is_(True))).scalars().unique()
    )


def notify(
    db: Session, recipients: list[User], event_type: str, title: str, body: str = "",
    request_id: int | None = None, link: str | None = None, at: datetime | None = None,
) -> list[NotificationEvent]:
    created = []
    seen = set()
    when = at or utcnow()
    for user in recipients:
        if user is None or user.id in seen:
            continue
        seen.add(user.id)
        created.append(NotificationEvent(
            recipient_id=user.id, channel="IN_APP", event_type=event_type, title=title, body=body,
            link=link, request_id=request_id, delivery_status="DELIVERED", created_at=when,
        ))
        for channel in EXTERNAL_CHANNELS.get(event_type, []):
            created.append(NotificationEvent(
                recipient_id=user.id, channel=channel, event_type=event_type, title=title, body=body, link=link,
                request_id=request_id, delivery_status=adapter.dispatch(channel, user, title, body), created_at=when,
            ))
    db.add_all(created)
    db.flush()
    return created
