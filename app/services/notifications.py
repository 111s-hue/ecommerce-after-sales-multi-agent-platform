from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.infrastructure.enterprise_models import notifications


class NotificationService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list_for_recipient(
        self, *, tenant_id: str, recipient_id: str, limit: int = 50
    ) -> dict[str, Any]:
        filters = (
            notifications.c.tenant_id == tenant_id,
            notifications.c.recipient_id == recipient_id,
        )
        with Session(self.engine) as session:
            rows = session.execute(
                select(notifications)
                .where(*filters)
                .order_by(notifications.c.created_at.desc())
                .limit(limit)
            ).all()
            unread = session.scalar(
                select(func.count())
                .select_from(notifications)
                .where(*filters, notifications.c.read_at.is_(None))
            )
            return {
                "unread": unread or 0,
                "items": [
                    {
                        key: value.isoformat() if isinstance(value, datetime) else value
                        for key, value in row._mapping.items()
                    }
                    for row in rows
                ],
            }

    def mark_read(self, *, tenant_id: str, recipient_id: str, notification_id: str) -> bool:
        now = datetime.now()
        with Session(self.engine) as session, session.begin():
            result = session.execute(
                update(notifications)
                .where(
                    notifications.c.tenant_id == tenant_id,
                    notifications.c.recipient_id == recipient_id,
                    notifications.c.notification_id == notification_id,
                )
                .values(read_at=now, status="read", updated_at=now)
            )
            return result.rowcount == 1
