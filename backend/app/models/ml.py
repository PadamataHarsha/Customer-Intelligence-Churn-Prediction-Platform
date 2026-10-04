"""ML models, predictions, training runs, and artifact ORM models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class MLModelRecord(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        CheckConstraint("task IN ('churn', 'revenue')", name="check_ml_model_task"),
        CheckConstraint(
            "status IN ('candidate', 'active', 'archived')", name="check_ml_model_status"
        ),
        Index("idx_ml_models_task_status", "task", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    feature_version: Mapped[str] = mapped_column(String, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    decision_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    artifact_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="model")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("task IN ('churn', 'revenue')", name="check_prediction_task"),
        CheckConstraint(
            "risk_category IN ('low', 'medium', 'high')", name="check_prediction_risk_category"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ml_models.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task: Mapped[str] = mapped_column(String, nullable=False)
    prediction_value: Mapped[float] = mapped_column(Float, nullable=False)
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    features_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="predictions")
    model: Mapped["MLModelRecord | None"] = relationship(
        "MLModelRecord", back_populates="predictions"
    )


class ModelTrainingRun(Base):
    __tablename__ = "model_training_runs"
    __table_args__ = (
        CheckConstraint("task IN ('churn', 'revenue')", name="check_run_task"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name="check_run_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task: Mapped[str] = mapped_column(String, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_key: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    artifact_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
