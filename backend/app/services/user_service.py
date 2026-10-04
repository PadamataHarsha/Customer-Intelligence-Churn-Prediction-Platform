"""User administration business logic service."""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.user import User
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserResponse, UserUpdate


class UserService:
    """Service handling user management and administrative updates."""

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> UserResponse:
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found", code="USER_NOT_FOUND")
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            is_active=bool(user.is_active),
            created_at=user.created_at,
        )

    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int = 50) -> list[UserResponse]:
        users = UserRepository.list_all(db, skip=skip, limit=limit)
        return [
            UserResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role.name,
                is_active=bool(u.is_active),
                created_at=u.created_at,
            )
            for u in users
        ]

    @staticmethod
    def update_user(
        db: Session,
        admin_user: User,
        user_id: int,
        req: UserUpdate,
        ip_address: str | None = None,
    ) -> UserResponse:
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found", code="USER_NOT_FOUND")

        changes: dict[str, str] = {}

        if req.full_name is not None and req.full_name != user.full_name:
            user.full_name = req.full_name
            changes["full_name"] = req.full_name

        if req.role is not None and req.role != user.role.name:
            new_role = UserRepository.get_role_by_name(db, req.role)
            if not new_role:
                raise NotFoundException(f"Role '{req.role}' not found", code="ROLE_NOT_FOUND")
            old_role_name = user.role.name
            user.role_id = new_role.id
            changes["old_role"] = old_role_name
            changes["new_role"] = req.role

            AuditLogRepository.log(
                db=db,
                user_id=admin_user.id,
                action="USER_ROLE_CHANGED",
                entity_type="user",
                entity_id=str(user.id),
                details={"old_role": old_role_name, "new_role": req.role},
                ip_address=ip_address,
            )

        if req.is_active is not None and req.is_active != bool(user.is_active):
            user.is_active = 1 if req.is_active else 0
            changes["is_active"] = str(req.is_active)

            AuditLogRepository.log(
                db=db,
                user_id=admin_user.id,
                action="USER_STATUS_CHANGED",
                entity_type="user",
                entity_id=str(user.id),
                details={"is_active": req.is_active},
                ip_address=ip_address,
            )

        db.commit()
        db.refresh(user)

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            is_active=bool(user.is_active),
            created_at=user.created_at,
        )
