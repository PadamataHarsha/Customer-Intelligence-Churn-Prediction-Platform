"""Security utilities: Argon2 password hashing and JWT issuance/verification."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedException

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2 hash."""
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Generates a signed JWT access token."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token_val = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return str(token_val)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT access token."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Access token has expired", code="TOKEN_EXPIRED") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException("Invalid access token", code="INVALID_TOKEN") from e
