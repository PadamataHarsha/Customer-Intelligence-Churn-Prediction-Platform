"""CustomerActivity ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class CustomerActivity(Base):
    __tablename__ = "customer_activity"
    __table_args__ = (
        CheckConstraint("activity_count >= 0", name="check_activity_count_non_negative"),
        CheckConstraint("duration_seconds >= 0", name="check_duration_seconds_non_negative"),
        Index("idx_activity_customer_time", "customer_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    activity_type: Mapped[str] = mapped_column(String, nullable=False)
    activity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="activities")
