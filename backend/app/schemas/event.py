"""Customer event schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerEventResponse(BaseModel):
    """Customer lifecycle event schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    event_type: str
    severity: str
    details_json: str
    timestamp: datetime
    created_at: datetime
