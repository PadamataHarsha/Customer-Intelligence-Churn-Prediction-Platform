"""Audit log persistence repository."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditLogRepository:
    """Repository handling immutable audit logging."""

    @staticmethod
    def log(
        db: Session,
        action: str,
        entity_type: str,
        user_id: int | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Creates and persists an audit log entry."""
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=json.dumps(details or {}),
            ip_address=ip_address,
            timestamp=datetime.now(UTC),
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry
