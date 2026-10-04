"""FastAPI dependency providers for authentication, authorization, and database."""

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)
limiter = Limiter(key_func=get_remote_address)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validates the bearer token and returns the authenticated user."""
    if not credentials or not credentials.credentials:
        raise UnauthorizedException("Authentication token is missing", code="MISSING_TOKEN")

    token = credentials.credentials
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("Invalid token payload", code="INVALID_TOKEN")

    try:
        user_id = int(user_id_str)
    except ValueError as e:
        raise UnauthorizedException("Invalid user ID in token", code="INVALID_TOKEN") from e

    stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User not found", code="USER_NOT_FOUND")

    if not user.is_active:
        raise UnauthorizedException("User account is deactivated", code="USER_DEACTIVATED")

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Dependency factory checking if current user has one of the required roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise ForbiddenException(
                f"Action requires one of the following roles: {', '.join(allowed_roles)}",
                code="FORBIDDEN_ROLE",
            )
        return current_user

    return role_checker
