"""Customer activity schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerActivityResponse(BaseModel):
    """Customer activity log schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    session_id: str | None
    activity_type: str
    activity_count: int
    duration_seconds: int
    timestamp: datetime
    created_at: datetime
