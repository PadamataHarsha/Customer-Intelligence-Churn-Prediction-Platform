"""User schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """Public user response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class UserRoleUpdate(BaseModel):
    """Schema for updating a user's role by an administrator."""

    role: Literal["admin", "analyst", "viewer"]


class UserStatusUpdate(BaseModel):
    """Schema for updating a user's active status."""

    is_active: bool


class UserUpdate(BaseModel):
    """Schema for modifying user attributes."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    role: Literal["admin", "analyst", "viewer"] | None = None
    is_active: bool | None = None
