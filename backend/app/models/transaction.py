"""Transaction ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.subscription import Subscription


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="check_txn_amount_cents_non_negative"),
        CheckConstraint("status IN ('succeeded', 'failed', 'refunded')", name="check_txn_status"),
        CheckConstraint("type IN ('payment', 'refund', 'chargeback')", name="check_txn_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String, nullable=False, default="succeeded", index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, default="payment")
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="transactions")
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="transactions"
    )
