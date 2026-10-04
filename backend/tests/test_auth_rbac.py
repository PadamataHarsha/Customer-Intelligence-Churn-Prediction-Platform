"""Comprehensive tests for Phase 3: Authentication, Authorization, RBAC, and CLI."""

from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.security import create_access_token
from app.main import app
from app.models import AuditLog, Base, Role, User

client = TestClient(app)


@pytest.fixture(name="db_session", autouse=True)
def setup_test_db() -> Generator[Session, None, None]:
    """Sets up an in-memory test database with default roles."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    # Populate base roles
    db.add(Role(id=1, name="admin", description="Admin"))
    db.add(Role(id=2, name="analyst", description="Analyst"))
    db.add(Role(id=3, name="viewer", description="Viewer"))
    db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app.dependency_overrides.clear()


def test_register_creates_viewer_only(db_session: Session) -> None:
    payload = {
        "email": "alice@example.com",
        "password": "SecurePassword123!",
        "full_name": "Alice Viewer",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["role"] == "viewer"
    assert data["is_active"] is True

    # Verify audit log
    audit = db_session.query(AuditLog).filter(AuditLog.action == "USER_REGISTERED").first()
    assert audit is not None
    assert audit.entity_id == str(data["id"])


def test_register_duplicate_email() -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
        "full_name": "First User",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_success_and_me() -> None:
    # 1. Register user
    reg_payload = {
        "email": "bob@example.com",
        "password": "Password123!",
        "full_name": "Bob Smith",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {"email": "bob@example.com", "password": "Password123!"}
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 3. Access /auth/me
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "bob@example.com"
    assert me_data["role"] == "viewer"


def test_login_invalid_password() -> None:
    reg_payload = {
        "email": "carol@example.com",
        "password": "CorrectPassword123!",
        "full_name": "Carol",
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "WrongPassword123!"},
    )
    assert login_resp.status_code == 401
    data = login_resp.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_user() -> None:
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword123!"},
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_and_invalid_tokens() -> None:
    # Missing token
    resp_missing = client.get("/api/v1/auth/me")
    assert resp_missing.status_code == 401
    assert resp_missing.json()["error"]["code"] == "MISSING_TOKEN"

    # Invalid token string
    resp_invalid = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )
    assert resp_invalid.status_code == 401
    assert resp_invalid.json()["error"]["code"] == "INVALID_TOKEN"

    # Expired token
    expired_token = create_access_token(
        subject=1, role="viewer", expires_delta=timedelta(seconds=-10)
    )
    resp_expired = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert resp_expired.status_code == 401
    assert resp_expired.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_rbac_admin_vs_viewer(db_session: Session) -> None:
    # 1. Create admin user
    from app.core.security import hash_password

    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin Test",
        role_id=1,
        is_active=1,
    )
    db_session.add(admin)
    db_session.commit()

    admin_token = create_access_token(subject=admin.id, role="admin")

    # 2. Create viewer user
    viewer = User(
        email="viewer@test.com",
        hashed_password=hash_password("ViewerPass123!"),
        full_name="Viewer Test",
        role_id=3,
        is_active=1,
    )
    db_session.add(viewer)
    db_session.commit()

    viewer_token = create_access_token(subject=viewer.id, role="viewer")

    # 3. Viewer attempts to access admin endpoint -> 403 Forbidden
    resp_forbidden = client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp_forbidden.status_code == 403
    assert resp_forbidden.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 4. Admin accesses admin endpoint -> 200 OK
    resp_admin = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_admin.status_code == 200
    user_list = resp_admin.json()
    assert len(user_list) >= 2

    # 5. Admin promotes viewer to analyst
    patch_resp = client.patch(
        f"/api/v1/users/{viewer.id}",
        json={"role": "analyst"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "analyst"

    # Verify audit log for role change
    audit = db_session.query(AuditLog).filter(AuditLog.action == "USER_ROLE_CHANGED").first()
    assert audit is not None
    assert audit.user_id == admin.id
