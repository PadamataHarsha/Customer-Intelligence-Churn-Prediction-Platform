"""Subscription business logic service."""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.user import User
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.plan_repo import PlanRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.schemas.common import PaginatedResponse
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)


class SubscriptionService:
    """Service handling subscription management."""

    @staticmethod
    def get_subscription(db: Session, subscription_id: int) -> SubscriptionResponse:
        sub = SubscriptionRepository.get_by_id(db, subscription_id)
        if not sub:
            raise NotFoundException(
                f"Subscription with ID {subscription_id} not found",
                code="SUBSCRIPTION_NOT_FOUND",
            )
        return SubscriptionResponse.model_validate(sub)

    @staticmethod
    def list_subscriptions(
        db: Session,
        status: str | None = None,
        customer_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[SubscriptionResponse]:
        skip = (page - 1) * page_size
        subs, total = SubscriptionRepository.list_all(
            db, status=status, customer_id=customer_id, skip=skip, limit=page_size
        )
        items = [SubscriptionResponse.model_validate(s) for s in subs]
        return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)

    @staticmethod
    def create_subscription(
        db: Session,
        payload: SubscriptionCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> SubscriptionResponse:
        customer = CustomerRepository.get_by_id(db, payload.customer_id)
        if not customer:
            raise NotFoundException(
                f"Customer with ID {payload.customer_id} not found",
                code="CUSTOMER_NOT_FOUND",
            )

        plan = PlanRepository.get_by_id(db, payload.plan_id)
        if not plan:
            raise NotFoundException(
                f"Plan with ID {payload.plan_id} not found",
                code="PLAN_NOT_FOUND",
            )

        sub = SubscriptionRepository.create(
            db=db,
            customer_id=payload.customer_id,
            plan_id=payload.plan_id,
            status=payload.status,
            current_period_start=payload.current_period_start,
            current_period_end=payload.current_period_end,
        )

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="SUBSCRIPTION_CREATED",
            entity_type="subscription",
            entity_id=str(sub.id),
            details={"customer_id": payload.customer_id, "plan_id": payload.plan_id},
            ip_address=ip_address,
        )

        return SubscriptionResponse.model_validate(sub)

    @staticmethod
    def update_subscription(
        db: Session,
        subscription_id: int,
        payload: SubscriptionUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> SubscriptionResponse:
        sub = SubscriptionRepository.get_by_id(db, subscription_id)
        if not sub:
            raise NotFoundException(
                f"Subscription with ID {subscription_id} not found",
                code="SUBSCRIPTION_NOT_FOUND",
            )

        if payload.plan_id is not None:
            plan = PlanRepository.get_by_id(db, payload.plan_id)
            if not plan:
                raise NotFoundException(
                    f"Plan with ID {payload.plan_id} not found",
                    code="PLAN_NOT_FOUND",
                )
            sub.plan_id = payload.plan_id

        if payload.status is not None:
            sub.status = payload.status
        if payload.current_period_start is not None:
            sub.current_period_start = payload.current_period_start
        if payload.current_period_end is not None:
            sub.current_period_end = payload.current_period_end
        if payload.cancelled_at is not None:
            sub.cancelled_at = payload.cancelled_at

        SubscriptionRepository.update(db, sub)

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="SUBSCRIPTION_UPDATED",
            entity_type="subscription",
            entity_id=str(sub.id),
            details={"status": sub.status},
            ip_address=ip_address,
        )

        return SubscriptionResponse.model_validate(sub)
