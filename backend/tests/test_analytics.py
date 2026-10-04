"""Comprehensive tests for Phase 5: Analytics and Segmentation."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, MLModelRecord, Prediction, Role, User

client = TestClient(app)

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "schema.sql"
SEED_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "seed.sql"


@pytest.fixture(name="empty_db_session")
def setup_empty_db() -> Generator[Session, None, None]:
    """Sets up an empty in-memory test database with only roles and a viewer user."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    viewer_role = Role(id=3, name="viewer", description="Viewer")
    db.add(viewer_role)
    viewer_user = User(
        id=1,
        email="viewer@example.com",
        hashed_password=hash_password("ViewerPass123!"),
        full_name="Viewer",
        role_id=3,
        is_active=1,
    )
    db.add(viewer_user)
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


@pytest.fixture(name="seeded_db_session")
def setup_seeded_db() -> Generator[Session, None, None]:
    """Sets up an in-memory test database loaded with full schema and seed.sql data."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Execute full schema and seed SQL
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            cursor.executescript(f.read())
        with open(SEED_PATH, encoding="utf-8") as f:
            cursor.executescript(f.read())
        raw_conn.commit()
    finally:
        raw_conn.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Add authenticated viewer user
    viewer_user = User(
        id=999,
        email="analyst@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="Analyst",
        role_id=2,
        is_active=1,
    )
    db.add(viewer_user)
    db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db

    db.close()
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def get_auth_headers() -> dict[str, str]:
    token = create_access_token(subject=1, role="viewer")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="seeded_auth_headers")
def get_seeded_auth_headers() -> dict[str, str]:
    token = create_access_token(subject=999, role="analyst")
    return {"Authorization": f"Bearer {token}"}


def test_empty_database_analytics_graceful(
    empty_db_session: Session, auth_headers: dict[str, str]
) -> None:
    """Verifies all analytics endpoints handle an empty database with zeroes/empty lists."""
    # 1. Overview
    resp_overview = client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert resp_overview.status_code == 200
    ov = resp_overview.json()
    assert ov["total_customers"] == 0
    assert ov["active_customers"] == 0
    assert ov["churned_customers"] == 0
    assert ov["churn_rate"] == 0.0
    assert ov["total_revenue_cents"] == 0
    assert ov["average_revenue_cents"] == 0.0
    assert ov["high_risk_count"] == 0
    assert ov["active_models"]["churn"] is None
    assert ov["active_models"]["revenue"] is None

    # 2. Revenue Trend
    resp_rev = client.get("/api/v1/analytics/revenue", headers=auth_headers)
    assert resp_rev.status_code == 200
    assert resp_rev.json() == []

    # 3. Churn Trend
    resp_churn = client.get("/api/v1/analytics/churn", headers=auth_headers)
    assert resp_churn.status_code == 200
    assert resp_churn.json() == []

    # 4. Customer Distribution
    resp_dist = client.get("/api/v1/analytics/customers", headers=auth_headers)
    assert resp_dist.status_code == 200
    dist = resp_dist.json()
    assert dist["total_customers"] == 0
    assert dist["by_status"] == []
    assert dist["by_acquisition_channel"] == []
    assert dist["by_region"] == []
    assert dist["by_industry"] == []
    assert dist["by_plan_tier"] == []

    # 5. Segments
    resp_seg = client.get("/api/v1/analytics/segments", headers=auth_headers)
    assert resp_seg.status_code == 200
    seg = resp_seg.json()
    assert seg["total_customers"] == 0
    assert seg["summary"] == []

    # 6. Activity Trend
    resp_act = client.get("/api/v1/analytics/activity", headers=auth_headers)
    assert resp_act.status_code == 200
    assert resp_act.json() == []


def test_seeded_data_analytics_overview(
    seeded_db_session: Session, seeded_auth_headers: dict[str, str]
) -> None:
    """Verifies analytics overview against hand-verified expected numbers from seed.sql."""
    resp = client.get("/api/v1/analytics/overview", headers=seeded_auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Hand-verified expectations for seed.sql (seed = 42):
    # Total customers: 200
    # Active: 145, Churned: 55
    # Churn rate: 55 / 200 = 0.275
    # Total revenue cents: 40,009,100
    # Average revenue cents: 40,009,100 / 200 = 200,045.5
    assert data["total_customers"] == 200
    assert data["active_customers"] == 145
    assert data["churned_customers"] == 55
    assert data["churn_rate"] == 0.275
    assert data["total_revenue_cents"] == 40009100
    assert data["average_revenue_cents"] == 200045.5
    assert data["high_risk_count"] == 0
    assert data["active_models"]["churn"] is None
    assert data["active_models"]["revenue"] is None


def test_seeded_data_revenue_and_churn_trends(
    seeded_db_session: Session, seeded_auth_headers: dict[str, str]
) -> None:
    """Tests revenue and churn time series trends against seeded database."""
    # 1. Revenue trend
    resp_rev = client.get("/api/v1/analytics/revenue", headers=seeded_auth_headers)
    assert resp_rev.status_code == 200
    rev_data = resp_rev.json()
    assert len(rev_data) > 0
    # Sum of all monthly revenues must match total revenue cents
    total_rev_sum = sum(item["revenue_cents"] for item in rev_data)
    assert total_rev_sum == 40009100
    # Check first period
    assert rev_data[0]["period"] == "2024-01"
    assert rev_data[0]["revenue_cents"] == 914500
    assert rev_data[0]["transaction_count"] == 11

    # 2. Churn trend
    resp_churn = client.get("/api/v1/analytics/churn", headers=seeded_auth_headers)
    assert resp_churn.status_code == 200
    churn_data = resp_churn.json()
    assert len(churn_data) > 0
    # Sum of monthly cancellations
    total_cancellations = sum(item["churned_count"] for item in churn_data)
    assert total_cancellations == 55


def test_seeded_data_customer_distribution(
    seeded_db_session: Session, seeded_auth_headers: dict[str, str]
) -> None:
    """Tests customer distributions across statuses, channels, regions, and tiers."""
    resp = client.get("/api/v1/analytics/customers", headers=seeded_auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_customers"] == 200

    # by_status check
    status_counts = {item["category"]: item["count"] for item in data["by_status"]}
    assert status_counts["active"] == 145
    assert status_counts["churned"] == 55

    # by_acquisition_channel check: total count must sum to 200
    channel_total = sum(item["count"] for item in data["by_acquisition_channel"])
    assert channel_total == 200

    # by_region check: total count must sum to 200
    region_total = sum(item["count"] for item in data["by_region"])
    assert region_total == 200

    # by_plan_tier check: counts must be present
    assert len(data["by_plan_tier"]) > 0


def test_seeded_data_rfm_segments(
    seeded_db_session: Session, seeded_auth_headers: dict[str, str]
) -> None:
    """Verifies RFM segmentation classifications and counts on seeded data."""
    resp = client.get("/api/v1/analytics/segments", headers=seeded_auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_customers"] == 200
    segment_counts = {item["segment"]: item["count"] for item in data["summary"]}

    # Hand-verified counts from seed dataset:
    # Loyal: 68, Champions: 62, Dormant: 56, At Risk: 14
    assert segment_counts["Loyal"] == 68
    assert segment_counts["Champions"] == 62
    assert segment_counts["Dormant"] == 56
    assert segment_counts["At Risk"] == 14
    assert sum(segment_counts.values()) == 200


def test_seeded_data_activity_trends(
    seeded_db_session: Session, seeded_auth_headers: dict[str, str]
) -> None:
    """Tests customer activity trends."""
    resp = client.get("/api/v1/analytics/activity", headers=seeded_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # Verify presence of expected fields
    point = data[0]
    assert "period" in point
    assert "activity_type" in point
    assert point["total_count"] > 0


def test_active_models_and_high_risk_overview(
    empty_db_session: Session, auth_headers: dict[str, str]
) -> None:
    """Verifies overview updates when an active model and high risk prediction are added."""
    # 1. Add active churn model
    model = MLModelRecord(
        name="Churn Classifier",
        task="churn",
        algorithm="RandomForestClassifier",
        version="churn_rf_v1",
        feature_version="v1",
        dataset_version="v1",
        metrics_json='{"f1": 0.85, "roc_auc": 0.91}',
        decision_threshold=0.45,
        status="active",
        artifact_key="churn_rf_v1.joblib",
    )
    empty_db_session.add(model)
    empty_db_session.flush()

    # 2. Add customer & high risk prediction
    from app.models.customer import Customer

    cust = Customer(
        external_id="cust_test_hr",
        name="High Risk Customer",
        email="hr@test.com",
        status="active",
    )
    empty_db_session.add(cust)
    empty_db_session.flush()

    pred = Prediction(
        customer_id=cust.id,
        model_id=model.id,
        task="churn",
        prediction_value=1.0,
        probability=0.88,
        risk_category="high",
        features_hash="hash_123",
    )
    empty_db_session.add(pred)
    empty_db_session.commit()

    resp = client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_customers"] == 1
    assert data["active_customers"] == 1
    assert data["high_risk_count"] == 1
    assert data["active_models"]["churn"] is not None
    assert data["active_models"]["churn"]["version"] == "churn_rf_v1"
    assert data["active_models"]["churn"]["algorithm"] == "RandomForestClassifier"
