"""Authentication and user management business logic service."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictException, NotFoundException, UnauthorizedException
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserResponse


class AuthService:
    """Service encapsulating user authentication and account lifecycle logic."""

    @staticmethod
    def register(db: Session, req: RegisterRequest, ip_address: str | None = None) -> UserResponse:
        existing = UserRepository.get_by_email(db, req.email)
        if existing:
            raise ConflictException(
                "A user with this email already exists", code="EMAIL_ALREADY_EXISTS"
            )

        viewer_role = UserRepository.get_role_by_name(db, "viewer")
        if not viewer_role:
            raise NotFoundException(
                "Viewer role not initialized in database", code="ROLE_NOT_FOUND"
            )

        hashed_pwd = hash_password(req.password)
        user = UserRepository.create(
            db=db,
            email=req.email,
            hashed_password=hashed_pwd,
            full_name=req.full_name,
            role_id=viewer_role.id,
            is_active=1,
        )

        AuditLogRepository.log(
            db=db,
            user_id=user.id,
            action="USER_REGISTERED",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": user.email, "role": "viewer"},
            ip_address=ip_address,
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role="viewer",
            is_active=True,
            created_at=user.created_at,
        )

    @staticmethod
    def login(db: Session, req: LoginRequest, ip_address: str | None = None) -> Token:
        user = UserRepository.get_by_email(db, req.email)
        # Generic error message to prevent user enumeration
        if not user or not verify_password(req.password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password", code="INVALID_CREDENTIALS")

        if not user.is_active:
            raise UnauthorizedException(
                "Account is disabled. Contact your administrator.", code="ACCOUNT_DISABLED"
            )

        token_str = create_access_token(subject=user.id, role=user.role.name)

        AuditLogRepository.log(
            db=db,
            user_id=user.id,
            action="USER_LOGIN_SUCCESS",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": user.email},
            ip_address=ip_address,
        )

        return Token(
            access_token=token_str,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def get_me(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            is_active=bool(user.is_active),
            created_at=user.created_at,
        )
