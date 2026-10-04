"""Subscription database repository."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription


class SubscriptionRepository:
    """Repository handling persistence for Subscriptions."""

    @staticmethod
    def get_by_id(db: Session, subscription_id: int) -> Subscription | None:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.plan))
            .where(Subscription.id == subscription_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_customer(
        db: Session,
        customer_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Subscription], int]:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.plan))
            .where(Subscription.customer_id == customer_id)
            .order_by(Subscription.created_at.desc())
        )
        count_stmt = select(func.count(Subscription.id)).where(
            Subscription.customer_id == customer_id
        )
        total = db.execute(count_stmt).scalar() or 0
        subs = list(db.execute(stmt.offset(skip).limit(limit)).scalars().all())
        return subs, total

    @staticmethod
    def list_all(
        db: Session,
        status: str | None = None,
        customer_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Subscription], int]:
        stmt = select(Subscription).options(joinedload(Subscription.plan))
        count_stmt = select(func.count(Subscription.id))

        if status:
            stmt = stmt.where(Subscription.status == status)
            count_stmt = count_stmt.where(Subscription.status == status)
        if customer_id:
            stmt = stmt.where(Subscription.customer_id == customer_id)
            count_stmt = count_stmt.where(Subscription.customer_id == customer_id)

        total = db.execute(count_stmt).scalar() or 0
        stmt = stmt.order_by(Subscription.created_at.desc()).offset(skip).limit(limit)
        subs = list(db.execute(stmt).scalars().all())
        return subs, total

    @staticmethod
    def create(
        db: Session,
        customer_id: int,
        plan_id: int,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
    ) -> Subscription:
        sub = Subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def update(db: Session, subscription: Subscription) -> Subscription:
        db.commit()
        db.refresh(subscription)
        return subscription
