"""Feature definitions, ordering, and validation schemas for ML."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

FEATURE_VERSION = "v1.0.0"

NUMERICAL_FEATURES: list[str] = [
    "tenure_days",
    "monthly_revenue",
    "total_revenue_to_date",
    "transaction_count_90d",
    "avg_transaction_value_90d",
    "days_since_last_activity",
    "activity_count_30d",
    "activity_count_90d",
    "login_frequency_30d",
    "support_ticket_count_90d",
    "payment_failure_count_90d",
    "engagement_score",
    "subscription_length_days",
]

CATEGORICAL_FEATURES: list[str] = [
    "plan_tier",
    "billing_cycle",
    "acquisition_channel",
    "region",
]

ALL_FEATURES: list[str] = NUMERICAL_FEATURES + CATEGORICAL_FEATURES


class RawCustomerFeatures(BaseModel):
    """Raw feature inputs for training and inference, matching the feature schema."""

    model_config = ConfigDict(extra="forbid")

    tenure_days: int = Field(ge=0, description="Customer tenure in days")
    monthly_revenue: float = Field(ge=0.0, description="Monthly subscription revenue in cents")
    total_revenue_to_date: float = Field(
        ge=0.0, description="Total settled revenue to date in cents"
    )
    transaction_count_90d: int = Field(
        ge=0, description="Number of settled payment transactions in trailing 90 days"
    )
    avg_transaction_value_90d: float = Field(
        ge=0.0, description="Average payment transaction amount in trailing 90 days in cents"
    )
    days_since_last_activity: int = Field(ge=0, description="Days since most recent activity")
    activity_count_30d: int = Field(ge=0, description="Activity count in trailing 30 days")
    activity_count_90d: int = Field(ge=0, description="Activity count in trailing 90 days")
    login_frequency_30d: int = Field(ge=0, description="Number of logins in trailing 30 days")
    support_ticket_count_90d: int = Field(
        ge=0, description="Support ticket events in trailing 90 days"
    )
    payment_failure_count_90d: int = Field(
        ge=0, description="Payment failure events or transactions in trailing 90 days"
    )
    engagement_score: float = Field(
        ge=0.0, le=100.0, description="Composite engagement score (0-100)"
    )
    subscription_length_days: int = Field(ge=0, description="Active subscription duration in days")

    # Categoricals
    plan_tier: str = Field(default="basic", description="Active plan tier")
    billing_cycle: str = Field(default="monthly", description="Billing cycle: monthly or annual")
    acquisition_channel: str = Field(
        default="organic_search", description="Customer acquisition channel"
    )
    region: str = Field(default="north_america", description="Customer geographical region")

    def to_dict(self) -> dict[str, Any]:
        """Converts model to dictionary preserving ALL_FEATURES order."""
        data = self.model_dump()
        return {feat: data[feat] for feat in ALL_FEATURES}

    def to_row(self) -> list[Any]:
        """Returns values in canonical column order for tabular preprocessing."""
        data = self.model_dump()
        return [data[feat] for feat in ALL_FEATURES]

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 hash of feature values."""
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
