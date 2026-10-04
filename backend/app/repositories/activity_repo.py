"""Customer activity repository."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity import CustomerActivity


class ActivityRepository:
    """Repository handling persistence for customer activity logs."""

    @staticmethod
    def list_by_customer(
        db: Session,
        customer_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CustomerActivity], int]:
        stmt = (
            select(CustomerActivity)
            .where(CustomerActivity.customer_id == customer_id)
            .order_by(CustomerActivity.timestamp.desc())
        )
        count_stmt = select(func.count(CustomerActivity.id)).where(
            CustomerActivity.customer_id == customer_id
        )
        total = db.execute(count_stmt).scalar() or 0
        items = list(db.execute(stmt.offset(skip).limit(limit)).scalars().all())
        return items, total
