"""Customer and CustomerProfile ORM models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.activity import CustomerActivity
    from app.models.event import CustomerEvent
    from app.models.ml import Prediction
    from app.models.segment import CustomerSegment
    from app.models.subscription import Subscription
    from app.models.transaction import Transaction


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'churned', 'paused')", name="check_customer_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="customer", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="customer", cascade="all, delete-orphan"
    )
    activities: Mapped[list["CustomerActivity"]] = relationship(
        "CustomerActivity", back_populates="customer", cascade="all, delete-orphan"
    )
    events: Mapped[list["CustomerEvent"]] = relationship(
        "CustomerEvent", back_populates="customer", cascade="all, delete-orphan"
    )
    segment: Mapped["CustomerSegment | None"] = relationship(
        "CustomerSegment", back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="customer", cascade="all, delete-orphan"
    )


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    acquisition_channel: Mapped[str] = mapped_column(String, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String, nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    company_size: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="profile")
