"""Transactions API router."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "",
    response_model=PaginatedResponse[TransactionResponse],
    summary="List transactions with filtering and pagination",
)
def list_transactions(
    customer_id: int | None = Query(None, description="Filter by customer ID"),
    status: str | None = Query(None, description="Filter by transaction status"),
    type: str | None = Query(None, description="Filter by transaction type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[TransactionResponse]:
    """Retrieves billing transactions."""
    return TransactionService.list_transactions(
        db=db,
        customer_id=customer_id,
        status=status,
        txn_type=type,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a billing transaction (Analyst/Admin)",
)
def create_transaction(
    payload: TransactionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analyst")),
) -> TransactionResponse:
    """Records a new billing transaction. Audited and restricted to analyst or admin."""
    client_ip = request.client.host if request.client else None
    return TransactionService.create_transaction(
        db=db, payload=payload, current_user=current_user, ip_address=client_ip
    )
