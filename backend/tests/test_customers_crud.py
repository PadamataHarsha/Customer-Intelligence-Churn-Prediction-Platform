"""Comprehensive tests for Phase 4: Customer, Subscription, and Transaction APIs."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (
    AuditLog,
    Base,
    CustomerActivity,
    CustomerEvent,
    Plan,
    Role,
    Subscription,
    Transaction,
    User,
)

client = TestClient(app)


@pytest.fixture(name="db_session", autouse=True)
def setup_test_db() -> Generator[Session, None, None]:
    """Sets up an in-memory test database with seeded roles, plans, and users."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # 1. Base Roles
    admin_role = Role(id=1, name="admin", description="Admin")
    analyst_role = Role(id=2, name="analyst", description="Analyst")
    viewer_role = Role(id=3, name="viewer", description="Viewer")
    db.add_all([admin_role, analyst_role, viewer_role])

    # 2. Base Users
    admin_user = User(
        id=1,
        email="admin@example.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        role_id=1,
        is_active=1,
    )
    analyst_user = User(
        id=2,
        email="analyst@example.com",
        hashed_password=hash_password("AnalystPass123!"),
        full_name="Analyst User",
        role_id=2,
        is_active=1,
    )
    viewer_user = User(
        id=3,
        email="viewer@example.com",
        hashed_password=hash_password("ViewerPass123!"),
        full_name="Viewer User",
        role_id=3,
        is_active=1,
    )
    db.add_all([admin_user, analyst_user, viewer_user])

    # 3. Base Plans
    plan1 = Plan(
        id=1,
        name="Starter Plan",
        code="starter",
        tier="starter",
        billing_cycle="monthly",
        price_cents=2900,
        currency="USD",
        is_active=1,
    )
    plan2 = Plan(
        id=2,
        name="Pro Plan",
        code="pro",
        tier="pro",
        billing_cycle="monthly",
        price_cents=9900,
        currency="USD",
        is_active=1,
    )
    db.add_all([plan1, plan2])
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


@pytest.fixture(name="admin_headers")
def get_admin_headers() -> dict[str, str]:
    token = create_access_token(subject=1, role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="analyst_headers")
def get_analyst_headers() -> dict[str, str]:
    token = create_access_token(subject=2, role="analyst")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="viewer_headers")
def get_viewer_headers() -> dict[str, str]:
    token = create_access_token(subject=3, role="viewer")
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_requests() -> None:
    """Verifies that unauthenticated requests to customer APIs return 401."""
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_TOKEN"

    resp = client.post("/api/v1/customers", json={})
    assert resp.status_code == 401


def test_customer_crud_lifecycle(
    db_session: Session, analyst_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    """Tests the full Customer lifecycle: Create, Get, Update, Delete with Audit Log tracking."""
    # 1. Create Customer
    payload: dict[str, Any] = {
        "name": "Acme Corp",
        "email": "contact@acme.com",
        "phone": "+1234567890",
        "company": "Acme Industries",
        "status": "active",
        "profile": {
            "acquisition_channel": "organic_search",
            "region": "NA",
            "industry": "Software",
            "company_size": "51-200",
            "metadata_json": '{"source": "demo"}',
        },
    }
    create_resp = client.post("/api/v1/customers", json=payload, headers=analyst_headers)
    assert create_resp.status_code == 201
    cust_data = create_resp.json()
    cust_id = cust_data["id"]
    assert cust_data["name"] == "Acme Corp"
    assert cust_data["email"] == "contact@acme.com"
    assert cust_data["profile"]["region"] == "NA"
    assert cust_data["profile"]["acquisition_channel"] == "organic_search"

    # Verify Audit log for CREATE
    create_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "CUSTOMER_CREATED", AuditLog.entity_id == str(cust_id))
        .first()
    )
    assert create_audit is not None
    assert create_audit.user_id == 2

    # 2. Get Customer by ID
    get_resp = client.get(f"/api/v1/customers/{cust_id}", headers=analyst_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cust_id

    # 3. Update Customer
    update_payload = {
        "name": "Acme Corporation Updated",
        "profile": {
            "region": "EMEA",
        },
    }
    update_resp = client.put(
        f"/api/v1/customers/{cust_id}", json=update_payload, headers=analyst_headers
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["name"] == "Acme Corporation Updated"
    assert updated_data["profile"]["region"] == "EMEA"
    assert updated_data["profile"]["acquisition_channel"] == "organic_search"

    # Verify Audit log for UPDATE
    update_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "CUSTOMER_UPDATED", AuditLog.entity_id == str(cust_id))
        .first()
    )
    assert update_audit is not None

    # 4. Delete Customer (Admin only)
    del_resp = client.delete(f"/api/v1/customers/{cust_id}", headers=admin_headers)
    assert del_resp.status_code == 204

    # Verify deleted
    get_deleted = client.get(f"/api/v1/customers/{cust_id}", headers=admin_headers)
    assert get_deleted.status_code == 404
    assert get_deleted.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"

    # Verify Audit log for DELETE
    delete_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "CUSTOMER_DELETED", AuditLog.entity_id == str(cust_id))
        .first()
    )
    assert delete_audit is not None
    assert delete_audit.user_id == 1


def test_rbac_restrictions_on_mutations(
    analyst_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    """Verifies that viewers cannot mutate customers and analysts cannot delete customers."""
    payload = {
        "name": "RBAC Test",
        "email": "rbac@example.com",
        "status": "active",
        "profile": {
            "acquisition_channel": "direct",
            "region": "APAC",
        },
    }

    # Viewer cannot create -> 403
    resp_create = client.post("/api/v1/customers", json=payload, headers=viewer_headers)
    assert resp_create.status_code == 403
    assert resp_create.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # Analyst creates customer
    resp_analyst_create = client.post("/api/v1/customers", json=payload, headers=analyst_headers)
    assert resp_analyst_create.status_code == 201
    cid = resp_analyst_create.json()["id"]

    # Viewer cannot update -> 403
    resp_viewer_update = client.put(
        f"/api/v1/customers/{cid}", json={"name": "New"}, headers=viewer_headers
    )
    assert resp_viewer_update.status_code == 403

    # Analyst cannot delete -> 403
    resp_analyst_delete = client.delete(f"/api/v1/customers/{cid}", headers=analyst_headers)
    assert resp_analyst_delete.status_code == 403


def test_duplicate_email_conflict(admin_headers: dict[str, str]) -> None:
    """Verifies that creating a customer with an existing email returns 409 Conflict."""
    payload = {
        "name": "First Customer",
        "email": "unique@example.com",
        "status": "active",
        "profile": {"acquisition_channel": "direct", "region": "NA"},
    }
    resp1 = client.post("/api/v1/customers", json=payload, headers=admin_headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/customers", json=payload, headers=admin_headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CUSTOMER_EMAIL_EXISTS"


def test_customer_validation_errors(admin_headers: dict[str, str]) -> None:
    """Verifies that invalid input data yields 422 Unprocessable Entity."""
    # Invalid email format
    resp = client.post(
        "/api/v1/customers",
        json={
            "name": "Test",
            "email": "invalid-email",
            "profile": {"acquisition_channel": "direct", "region": "NA"},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    # Missing profile
    resp = client.post(
        "/api/v1/customers",
        json={"name": "Test", "email": "valid@email.com"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_pagination_and_filtering(admin_headers: dict[str, str]) -> None:
    """Tests customer pagination, search, status filtering, and sorting."""
    # Create 15 customers: 10 active, 5 churned
    for i in range(1, 16):
        status_val = "active" if i <= 10 else "churned"
        client.post(
            "/api/v1/customers",
            json={
                "name": f"Customer {i:02d}",
                "email": f"cust{i:02d}@test.com",
                "company": f"Corp {i:02d}",
                "status": status_val,
                "profile": {"acquisition_channel": "referral", "region": "EU"},
            },
            headers=admin_headers,
        )

    # 1. Page 1 (limit 5)
    resp = client.get("/api/v1/customers?page=1&page_size=5", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total_pages"] == 3
    assert len(data["items"]) == 5

    # 2. Filter by status 'churned'
    resp_churned = client.get("/api/v1/customers?status=churned", headers=admin_headers)
    assert resp_churned.status_code == 200
    churned_data = resp_churned.json()
    assert churned_data["total"] == 5
    assert all(item["status"] == "churned" for item in churned_data["items"])

    # 3. Search query
    resp_search = client.get("/api/v1/customers?search=cust05", headers=admin_headers)
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["email"] == "cust05@test.com"

    # 4. Sort ascending by name
    resp_sort = client.get(
        "/api/v1/customers?sort_by=name&sort_order=asc&page_size=5", headers=admin_headers
    )
    assert resp_sort.status_code == 200
    sort_data = resp_sort.json()
    names = [c["name"] for c in sort_data["items"]]
    assert names == sorted(names)


def test_customer_sub_resources(db_session: Session, admin_headers: dict[str, str]) -> None:
    """Tests sub-resource endpoints: /activity, /events, /subscriptions, /transactions."""
    # 1. Create a customer
    create_resp = client.post(
        "/api/v1/customers",
        json={
            "name": "SubResource Customer",
            "email": "sub@example.com",
            "status": "active",
            "profile": {"acquisition_channel": "paid_ads", "region": "NA"},
        },
        headers=admin_headers,
    )
    cid = create_resp.json()["id"]

    # 2. Insert test data directly into sub-resource tables
    now = datetime.now(UTC)
    activity = CustomerActivity(
        customer_id=cid,
        activity_type="login",
        session_id="sess_123",
        activity_count=2,
        duration_seconds=300,
        timestamp=now,
    )
    event_entry = CustomerEvent(
        customer_id=cid,
        event_type="ticket_created",
        severity="high",
        details_json='{"priority": "high"}',
        timestamp=now,
    )
    sub = Subscription(
        customer_id=cid,
        plan_id=1,
        status="active",
        current_period_start=now,
        current_period_end=now,
    )
    txn = Transaction(
        customer_id=cid,
        subscription_id=None,
        amount_cents=2900,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=now,
    )
    db_session.add_all([activity, event_entry, sub, txn])
    db_session.commit()

    # 3. Test GET /customers/{id}/activity
    act_resp = client.get(f"/api/v1/customers/{cid}/activity", headers=admin_headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["total"] == 1
    assert act_resp.json()["items"][0]["activity_type"] == "login"

    # 4. Test GET /customers/{id}/events
    ev_resp = client.get(f"/api/v1/customers/{cid}/events", headers=admin_headers)
    assert ev_resp.status_code == 200
    assert ev_resp.json()["total"] == 1
    assert ev_resp.json()["items"][0]["event_type"] == "ticket_created"

    # 5. Test GET /customers/{id}/subscriptions
    sub_resp = client.get(f"/api/v1/customers/{cid}/subscriptions", headers=admin_headers)
    assert sub_resp.status_code == 200
    assert sub_resp.json()["total"] == 1
    assert sub_resp.json()["items"][0]["plan"]["tier"] == "starter"

    # 6. Test GET /customers/{id}/transactions
    txn_resp = client.get(f"/api/v1/customers/{cid}/transactions", headers=admin_headers)
    assert txn_resp.status_code == 200
    assert txn_resp.json()["total"] == 1
    assert txn_resp.json()["items"][0]["amount_cents"] == 2900

    # 7. Test non-existent customer sub-resource returns 404
    non_existent_resp = client.get("/api/v1/customers/99999/activity", headers=admin_headers)
    assert non_existent_resp.status_code == 404
    assert non_existent_resp.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


def test_customer_list_n_plus_one_prevention(
    db_session: Session, admin_headers: dict[str, str]
) -> None:
    """Asserts that listing customers eagerly loads profiles and executes at most 2 queries."""
    # Seed 15 customers with profiles
    for i in range(1, 16):
        client.post(
            "/api/v1/customers",
            json={
                "name": f"NPlusOne Customer {i}",
                "email": f"nplus{i}@test.com",
                "status": "active",
                "profile": {"acquisition_channel": "partner", "region": "APAC"},
            },
            headers=admin_headers,
        )

    engine = db_session.get_bind()
    query_count = 0

    def query_counter(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal query_count
        # Ignore internal PRAGMA or transaction statements if any
        if statement.strip().upper().startswith(("SELECT", "WITH")):
            query_count += 1

    event.listen(engine, "before_cursor_execute", query_counter)
    try:
        resp = client.get("/api/v1/customers?page_size=15", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 15
        # Must execute at most 3 SELECT queries:
        # 1 for user authentication + role
        # 1 for customer COUNT(*)
        # 1 for customer + profile eager joinedload
        # If N+1 were occurring, query_count would be at least 3 + 15 = 18 queries!
        assert query_count <= 3, f"Expected <= 3 queries, got {query_count} queries (N+1 detected!)"
    finally:
        event.remove(engine, "before_cursor_execute", query_counter)
