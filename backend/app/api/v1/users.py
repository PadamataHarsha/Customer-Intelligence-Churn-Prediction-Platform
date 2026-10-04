"""User management endpoints (admin only)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List all users (Admin only)",
)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[UserResponse]:
    """Retrieves a paginated list of all system users. Requires admin privileges."""
    return UserService.list_users(db=db, skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details by ID (Admin only)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> UserResponse:
    """Retrieves detailed user record by ID. Requires admin privileges."""
    return UserService.get_user_by_id(db=db, user_id=user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user role or active status (Admin only)",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin")),
) -> UserResponse:
    """Updates a user's role or status. All modifications are logged to the audit trail."""
    client_ip = request.client.host if request.client else None
    return UserService.update_user(
        db=db,
        admin_user=admin_user,
        user_id=user_id,
        req=payload,
        ip_address=client_ip,
    )
