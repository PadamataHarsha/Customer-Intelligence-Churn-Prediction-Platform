"""User and Role database repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.role import Role
from app.models.user import User


class UserRepository:
    """Repository handling persistence for Users and Roles."""

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User | None:
        stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).options(joinedload(User.role)).where(User.email == email.lower())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_role_by_name(db: Session, role_name: str) -> Role | None:
        stmt = select(Role).where(Role.name == role_name)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        email: str,
        hashed_password: str,
        full_name: str,
        role_id: int,
        is_active: int = 1,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            role_id=role_id,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_all(
        db: Session,
        skip: int = 0,
        limit: int = 50,
    ) -> list[User]:
        stmt = (
            select(User).options(joinedload(User.role)).order_by(User.id).offset(skip).limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def count(db: Session) -> int:
        stmt = select(User.id)
        return len(db.execute(stmt).all())
