"""Transaction API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    """Payload to record a billing transaction."""

    customer_id: int
    subscription_id: int | None = None
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="USD", max_length=10)
    status: Literal["succeeded", "failed", "refunded"] = "succeeded"
    type: Literal["payment", "refund", "chargeback"] = "payment"
    transaction_date: datetime | None = None


class TransactionResponse(BaseModel):
    """Complete transaction response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    subscription_id: int | None
    amount_cents: int
    currency: str
    status: str
    type: str
    transaction_date: datetime
    created_at: datetime
