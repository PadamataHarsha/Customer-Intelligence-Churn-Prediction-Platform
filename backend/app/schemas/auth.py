"""Authentication schemas."""

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """Access token response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class LoginRequest(BaseModel):
    """User login request schema."""

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    """User registration request schema (always creates viewer role)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
