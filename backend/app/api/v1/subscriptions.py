"""Subscription management API router."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get(
    "",
    response_model=PaginatedResponse[SubscriptionResponse],
    summary="List subscriptions with filtering and pagination",
)
def list_subscriptions(
    status: str | None = Query(
        None, description="Filter by status ('active', 'cancelled', 'past_due', 'paused')"
    ),
    customer_id: int | None = Query(None, description="Filter by customer ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[SubscriptionResponse]:
    """Retrieves paginated subscriptions. Accessible by all authenticated users."""
    return SubscriptionService.list_subscriptions(
        db=db, status=status, customer_id=customer_id, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subscription (Analyst/Admin)",
)
def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analyst")),
) -> SubscriptionResponse:
    """Creates a new customer subscription. Audited and restricted to analyst or admin."""
    client_ip = request.client.host if request.client else None
    return SubscriptionService.create_subscription(
        db=db, payload=payload, current_user=current_user, ip_address=client_ip
    )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get subscription by ID",
)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SubscriptionResponse:
    return SubscriptionService.get_subscription(db=db, subscription_id=subscription_id)


@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Update subscription state (Analyst/Admin)",
)
def update_subscription(
    subscription_id: int,
    payload: SubscriptionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analyst")),
) -> SubscriptionResponse:
    """Modifies subscription status or plan. Audited and restricted to analyst or admin."""
    client_ip = request.client.host if request.client else None
    return SubscriptionService.update_subscription(
        db=db,
        subscription_id=subscription_id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )
