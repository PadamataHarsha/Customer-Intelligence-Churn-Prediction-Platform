"""Subscription API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.plan import PlanResponse


class SubscriptionCreate(BaseModel):
    """Payload to create a customer subscription."""

    customer_id: int
    plan_id: int
    status: Literal["active", "cancelled", "past_due", "paused"] = "active"
    current_period_start: datetime
    current_period_end: datetime


class SubscriptionUpdate(BaseModel):
    """Payload to update subscription state."""

    plan_id: int | None = None
    status: Literal["active", "cancelled", "past_due", "paused"] | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancelled_at: datetime | None = None


class SubscriptionResponse(BaseModel):
    """Complete subscription response including associated plan."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    plan_id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    plan: PlanResponse | None = None
