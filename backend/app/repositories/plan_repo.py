"""Plan database repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan


class PlanRepository:
    """Repository handling persistence for Subscription Plans."""

    @staticmethod
    def get_by_id(db: Session, plan_id: int) -> Plan | None:
        return db.get(Plan, plan_id)

    @staticmethod
    def list_all(db: Session, active_only: bool = True) -> list[Plan]:
        stmt = select(Plan).order_by(Plan.price_cents.asc())
        if active_only:
            stmt = stmt.where(Plan.is_active == 1)
        return list(db.execute(stmt).scalars().all())
