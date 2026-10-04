"""Customer events repository."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import CustomerEvent


class EventRepository:
    """Repository handling persistence for customer events."""

    @staticmethod
    def list_by_customer(
        db: Session,
        customer_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CustomerEvent], int]:
        stmt = (
            select(CustomerEvent)
            .where(CustomerEvent.customer_id == customer_id)
            .order_by(CustomerEvent.timestamp.desc())
        )
        count_stmt = select(func.count(CustomerEvent.id)).where(
            CustomerEvent.customer_id == customer_id
        )
        total = db.execute(count_stmt).scalar() or 0
        items = list(db.execute(stmt.offset(skip).limit(limit)).scalars().all())
        return items, total
