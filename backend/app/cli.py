"""Command-line interface utilities for platform administration."""

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Base
from app.models.role import Role
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.user_repo import UserRepository


def ensure_roles(db: Session) -> None:
    """Ensures base roles exist in the database."""
    bind = db.get_bind()
    if bind is not None:
        Base.metadata.create_all(bind=bind)
    roles = [
        ("admin", "Administrator with full system privileges"),
        ("analyst", "Analyst with customer and ML experimentation privileges"),
        ("viewer", "Read-only viewer"),
    ]
    for name, desc in roles:
        r = db.query(Role).filter(Role.name == name).first()
        if not r:
            db.add(Role(name=name, description=desc))
    db.commit()


def create_admin_cmd(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        ensure_roles(db)
        email = args.email.lower()
        password = args.password
        if not password:
            password = getpass.getpass("Enter admin password: ")
            confirm = getpass.getpass("Confirm admin password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)

        if len(password) < 8:
            print("Error: Password must be at least 8 characters.", file=sys.stderr)
            sys.exit(1)

        admin_role = UserRepository.get_role_by_name(db, "admin")
        if not admin_role:
            print("Error: Admin role not found.", file=sys.stderr)
            sys.exit(1)

        user = UserRepository.get_by_email(db, email)
        hashed = hash_password(password)

        if user:
            user.hashed_password = hashed
            user.role_id = admin_role.id
            user.is_active = 1
            if args.name:
                user.full_name = args.name
            db.commit()
            print(f"Updated existing user '{email}' to administrator.")
        else:
            name = args.name or "System Administrator"
            user = UserRepository.create(
                db=db,
                email=email,
                hashed_password=hashed,
                full_name=name,
                role_id=admin_role.id,
                is_active=1,
            )
            print(f"Created new administrator account '{email}'.")

        AuditLogRepository.log(
            db=db,
            user_id=user.id,
            action="CLI_CREATE_ADMIN",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": email},
        )
    finally:
        db.close()


def create_user_cmd(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        ensure_roles(db)
        email = args.email.lower()
        role_name = args.role.lower()
        password = args.password

        if not password:
            password = getpass.getpass(f"Enter password for {email}: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)

        role = UserRepository.get_role_by_name(db, role_name)
        if not role:
            print(f"Error: Role '{role_name}' does not exist.", file=sys.stderr)
            sys.exit(1)

        user = UserRepository.get_by_email(db, email)
        hashed = hash_password(password)

        if user:
            user.hashed_password = hashed
            user.role_id = role.id
            if args.name:
                user.full_name = args.name
            db.commit()
            print(f"Updated existing user '{email}' with role '{role_name}'.")
        else:
            name = args.name or f"{role_name.capitalize()} User"
            user = UserRepository.create(
                db=db,
                email=email,
                hashed_password=hashed,
                full_name=name,
                role_id=role.id,
                is_active=1,
            )
            print(f"Created new user '{email}' with role '{role_name}'.")

        AuditLogRepository.log(
            db=db,
            user_id=user.id,
            action="CLI_CREATE_USER",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": email, "role": role_name},
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Customer Intelligence Platform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create or promote an administrator")
    admin_parser.add_argument("--email", required=True, help="Administrator email address")
    admin_parser.add_argument("--password", required=False, help="Administrator password")
    admin_parser.add_argument("--name", required=False, help="Full name")
    admin_parser.set_defaults(func=create_admin_cmd)

    # create-user
    user_parser = subparsers.add_parser("create-user", help="Create a user with specified role")
    user_parser.add_argument("--email", required=True, help="User email address")
    user_parser.add_argument(
        "--role", required=True, choices=["admin", "analyst", "viewer"], help="Assigned role"
    )
    user_parser.add_argument("--password", required=False, help="User password")
    user_parser.add_argument("--name", required=False, help="Full name")
    user_parser.set_defaults(func=create_user_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
