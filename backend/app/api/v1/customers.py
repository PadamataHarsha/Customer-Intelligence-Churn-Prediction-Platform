"""Customer management and sub-resource API endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import CustomerActivityResponse
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.event import CustomerEventResponse
from app.schemas.subscription import SubscriptionResponse
from app.schemas.transaction import TransactionResponse
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List customers with filtering and pagination",
)
def list_customers(
    status: str | None = Query(
        None, description="Filter by status ('active', 'churned', 'paused')"
    ),
    search: str | None = Query(None, description="Search query by name, email, or company"),
    sort_by: str = Query(
        "created_at",
        description="Field to sort by ('created_at', 'name', 'email', 'status', 'id')",
    ),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[CustomerResponse]:
    """Returns a paginated list of customers. Readable by all authenticated users."""
    return CustomerService.list_customers(
        db=db,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer and profile (Analyst/Admin)",
)
def create_customer(
    payload: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analyst")),
) -> CustomerResponse:
    """Creates a new customer with demographic profile. Requires analyst or admin role."""
    client_ip = request.client.host if request.client else None
    return CustomerService.create_customer(
        db=db,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve customer details by ID",
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CustomerResponse:
    """Retrieves complete customer details by ID."""
    return CustomerService.get_customer(db=db, customer_id=customer_id)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer attributes (Analyst/Admin)",
)
@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer attributes (Analyst/Admin)",
)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analyst")),
) -> CustomerResponse:
    """Modifies customer details. Audited and restricted to analyst or admin."""
    client_ip = request.client.host if request.client else None
    return CustomerService.update_customer(
        db=db,
        customer_id=customer_id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer (Admin only)",
)
def delete_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> None:
    """Deletes customer and cascaded records. Audited and restricted to analyst or admin."""
    client_ip = request.client.host if request.client else None
    CustomerService.delete_customer(
        db=db,
        customer_id=customer_id,
        current_user=current_user,
        ip_address=client_ip,
    )


# --- Sub-resources ---


@router.get(
    "/{customer_id}/activity",
    response_model=PaginatedResponse[CustomerActivityResponse],
    summary="Get customer activity history",
)
def get_customer_activity(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[CustomerActivityResponse]:
    return CustomerService.get_activity(
        db=db, customer_id=customer_id, page=page, page_size=page_size
    )


@router.get(
    "/{customer_id}/events",
    response_model=PaginatedResponse[CustomerEventResponse],
    summary="Get customer lifecycle events",
)
def get_customer_events(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[CustomerEventResponse]:
    return CustomerService.get_events(
        db=db, customer_id=customer_id, page=page, page_size=page_size
    )


@router.get(
    "/{customer_id}/subscriptions",
    response_model=PaginatedResponse[SubscriptionResponse],
    summary="Get customer subscriptions",
)
def get_customer_subscriptions(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[SubscriptionResponse]:
    return CustomerService.get_subscriptions(
        db=db, customer_id=customer_id, page=page, page_size=page_size
    )


@router.get(
    "/{customer_id}/transactions",
    response_model=PaginatedResponse[TransactionResponse],
    summary="Get customer billing transactions",
)
def get_customer_transactions(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[TransactionResponse]:
    return CustomerService.get_transactions(
        db=db, customer_id=customer_id, page=page, page_size=page_size
    )
