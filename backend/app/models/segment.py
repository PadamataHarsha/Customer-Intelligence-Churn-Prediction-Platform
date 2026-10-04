"""CustomerSegment ORM model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class CustomerSegment(Base):
    __tablename__ = "customer_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    segment_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rfm_score_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="segment")
