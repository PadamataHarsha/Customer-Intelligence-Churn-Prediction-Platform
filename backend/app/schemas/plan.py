"""Plan API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanResponse(BaseModel):
    """Subscription plan response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    tier: str
    billing_cycle: str
    price_cents: int
    currency: str
    is_active: int
    created_at: datetime
