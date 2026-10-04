"""Authentication endpoints: register, login, me."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user (viewer role)",
)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Public registration. All new users are assigned the 'viewer' role by default."""
    client_ip = request.client.host if request.client else None
    return AuthService.register(db=db, req=payload, ip_address=client_ip)


@router.post(
    "/login",
    response_model=Token,
    summary="User login with JWT generation",
)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    """Authenticates credentials and returns a signed bearer access token."""
    client_ip = request.client.host if request.client else None
    return AuthService.login(db=db, req=payload, ip_address=client_ip)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve current user profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns profile and assigned role for the authenticated user."""
    return AuthService.get_me(current_user)
