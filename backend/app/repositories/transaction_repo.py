"""Transaction database repository."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


class TransactionRepository:
    """Repository handling persistence for billing transactions."""

    @staticmethod
    def get_by_id(db: Session, transaction_id: int) -> Transaction | None:
        return db.get(Transaction, transaction_id)

    @staticmethod
    def list_transactions(
        db: Session,
        customer_id: int | None = None,
        status: str | None = None,
        txn_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        stmt = select(Transaction)
        count_stmt = select(func.count(Transaction.id))

        if customer_id:
            stmt = stmt.where(Transaction.customer_id == customer_id)
            count_stmt = count_stmt.where(Transaction.customer_id == customer_id)
        if status:
            stmt = stmt.where(Transaction.status == status)
            count_stmt = count_stmt.where(Transaction.status == status)
        if txn_type:
            stmt = stmt.where(Transaction.type == txn_type)
            count_stmt = count_stmt.where(Transaction.type == txn_type)

        total = db.execute(count_stmt).scalar() or 0
        stmt = stmt.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit)
        txns = list(db.execute(stmt).scalars().all())
        return txns, total

    @staticmethod
    def create(
        db: Session,
        customer_id: int,
        amount_cents: int,
        currency: str,
        status: str,
        txn_type: str,
        subscription_id: int | None = None,
        transaction_date: datetime | None = None,
    ) -> Transaction:
        txn = Transaction(
            customer_id=customer_id,
            subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            status=status,
            type=txn_type,
            transaction_date=transaction_date or datetime.now(),
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return txn
