"""Transaction business logic service."""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.user import User
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.common import PaginatedResponse
from app.schemas.transaction import TransactionCreate, TransactionResponse


class TransactionService:
    """Service handling billing transactions."""

    @staticmethod
    def list_transactions(
        db: Session,
        customer_id: int | None = None,
        status: str | None = None,
        txn_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[TransactionResponse]:
        skip = (page - 1) * page_size
        txns, total = TransactionRepository.list_transactions(
            db,
            customer_id=customer_id,
            status=status,
            txn_type=txn_type,
            skip=skip,
            limit=page_size,
        )
        items = [TransactionResponse.model_validate(t) for t in txns]
        return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)

    @staticmethod
    def create_transaction(
        db: Session,
        payload: TransactionCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> TransactionResponse:
        customer = CustomerRepository.get_by_id(db, payload.customer_id)
        if not customer:
            raise NotFoundException(
                f"Customer with ID {payload.customer_id} not found",
                code="CUSTOMER_NOT_FOUND",
            )

        txn = TransactionRepository.create(
            db=db,
            customer_id=payload.customer_id,
            subscription_id=payload.subscription_id,
            amount_cents=payload.amount_cents,
            currency=payload.currency,
            status=payload.status,
            txn_type=payload.type,
            transaction_date=payload.transaction_date,
        )

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="TRANSACTION_RECORDED",
            entity_type="transaction",
            entity_id=str(txn.id),
            details={"customer_id": payload.customer_id, "amount_cents": payload.amount_cents},
            ip_address=ip_address,
        )

        return TransactionResponse.model_validate(txn)
