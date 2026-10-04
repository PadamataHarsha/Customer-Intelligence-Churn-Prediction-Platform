"""Customer and CustomerProfile API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerProfileCreate(BaseModel):
    """Profile payload when creating a customer."""

    acquisition_channel: str = Field(min_length=2, max_length=50)
    region: str = Field(min_length=2, max_length=50)
    industry: str | None = Field(default=None, max_length=50)
    company_size: str | None = Field(default=None, max_length=50)
    metadata_json: str = "{}"


class CustomerProfileUpdate(BaseModel):
    """Profile payload when updating customer profile."""

    acquisition_channel: str | None = Field(default=None, min_length=2, max_length=50)
    region: str | None = Field(default=None, min_length=2, max_length=50)
    industry: str | None = None
    company_size: str | None = None
    metadata_json: str | None = None


class CustomerProfileResponse(BaseModel):
    """Customer profile response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    acquisition_channel: str
    region: str
    industry: str | None
    company_size: str | None
    metadata_json: str
    created_at: datetime


class CustomerCreate(BaseModel):
    """Payload to create a new customer."""

    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=100)
    status: Literal["active", "churned", "paused"] = "active"
    profile: CustomerProfileCreate


class CustomerUpdate(BaseModel):
    """Payload to update an existing customer."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = None
    company: str | None = None
    status: Literal["active", "churned", "paused"] | None = None
    profile: CustomerProfileUpdate | None = None


class CustomerResponse(BaseModel):
    """Complete customer representation including profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    email: EmailStr
    phone: str | None
    company: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    profile: CustomerProfileResponse | None = None
