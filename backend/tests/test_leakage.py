"""Leakage prevention, label window validation, and feature engineering tests."""

from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ml.datasets.generate import generate_synthetic_panel_dataset
from app.ml.datasets.panel_builder import PanelDatasetBuilder
from app.ml.features.extractor import FeatureEngineeringService
from app.ml.features.schemas import ALL_FEATURES, RawCustomerFeatures
from app.models import (
    Base,
    Customer,
    CustomerActivity,
    CustomerEvent,
    CustomerProfile,
    Plan,
    Subscription,
    Transaction,
)


@pytest.fixture(name="db_session")
def setup_test_db() -> Generator[Session, None, None]:
    """Sets up an in-memory test database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed basic plan
    plan = Plan(
        id=1,
        name="Pro Monthly",
        code="plan_pro_m",
        tier="pro",
        billing_cycle="monthly",
        price_cents=7900,
        currency="USD",
        is_active=1,
    )
    db.add(plan)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_feature_leakage_immunity(db_session: Session) -> None:
    """Proves mutating data after snapshot T does not alter features computed at T."""
    t_snapshot = datetime(2025, 6, 1, 12, 0, 0)
    created_at = t_snapshot - timedelta(days=60)

    # 1. Create customer and history strictly before T
    cust = Customer(
        id=101,
        external_id="cust_leak_test",
        name="Leakage Test User",
        email="leak@test.com",
        created_at=created_at,
        status="active",
    )
    prof = CustomerProfile(
        customer_id=101,
        acquisition_channel="organic_search",
        region="north_america",
    )
    sub = Subscription(
        id=101,
        customer_id=101,
        plan_id=1,
        status="active",
        current_period_start=created_at,
        current_period_end=created_at + timedelta(days=365),
    )
    txn_past = Transaction(
        id=101,
        customer_id=101,
        amount_cents=7900,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_snapshot - timedelta(days=10),
    )
    act_past = CustomerActivity(
        id=101,
        customer_id=101,
        activity_type="login",
        activity_count=3,
        duration_seconds=300,
        timestamp=t_snapshot - timedelta(days=5),
    )
    db_session.add_all([cust, prof, sub, txn_past, act_past])
    db_session.commit()

    # Compute features at T
    feats_before = FeatureEngineeringService.compute_features_for_customer(
        db_session, 101, as_of=t_snapshot
    )

    # 2. Add extensive mutations strictly AFTER T
    t_future = t_snapshot + timedelta(days=10)
    txn_future = Transaction(
        id=102,
        customer_id=101,
        amount_cents=999999,  # huge payment after T
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_future,
    )
    act_future = CustomerActivity(
        id=102,
        customer_id=101,
        activity_type="login",
        activity_count=100,  # massive usage after T
        duration_seconds=50000,
        timestamp=t_future,
    )
    event_future = CustomerEvent(
        id=101,
        customer_id=101,
        event_type="support_ticket",
        severity="high",
        details_json="{}",
        timestamp=t_future,
    )
    # Cancel subscription after T
    sub.cancelled_at = t_snapshot + timedelta(days=15)

    db_session.add_all([txn_future, act_future, event_future])
    db_session.commit()

    # Re-compute features at T
    feats_after = FeatureEngineeringService.compute_features_for_customer(
        db_session, 101, as_of=t_snapshot
    )

    # Absolute equality proof: zero leakage
    assert feats_before.to_dict() == feats_after.to_dict()
    assert feats_before.compute_hash() == feats_after.compute_hash()
    assert feats_after.total_revenue_to_date == 7900.0
    assert feats_after.transaction_count_90d == 1
    assert feats_after.support_ticket_count_90d == 0
    assert feats_after.plan_tier == "pro"


def test_excluded_customers_at_snapshot(db_session: Session) -> None:
    """Proves customers not yet created or already churned at T are excluded."""
    t_snapshot = datetime(2025, 6, 1, 12, 0, 0)

    # Customer 1: Created AFTER T -> Excluded
    cust_future = Customer(
        id=201,
        external_id="c_future",
        name="Future User",
        email="fut@test.com",
        created_at=t_snapshot + timedelta(days=5),
        status="active",
    )
    sub_future = Subscription(
        id=201,
        customer_id=201,
        plan_id=1,
        status="active",
        current_period_start=t_snapshot + timedelta(days=5),
        current_period_end=t_snapshot + timedelta(days=35),
    )

    # Customer 2: Created before T, but cancelled BEFORE T -> Excluded
    cust_churned = Customer(
        id=202,
        external_id="c_churned",
        name="Churned Past User",
        email="churn@test.com",
        created_at=t_snapshot - timedelta(days=100),
        status="churned",
    )
    sub_churned = Subscription(
        id=202,
        customer_id=202,
        plan_id=1,
        status="cancelled",
        current_period_start=t_snapshot - timedelta(days=100),
        current_period_end=t_snapshot - timedelta(days=10),
        cancelled_at=t_snapshot - timedelta(days=10),  # churned 10 days before T
    )

    # Customer 3: Created before T, ACTIVE at T -> Eligible
    cust_active = Customer(
        id=203,
        external_id="c_active",
        name="Active User",
        email="act@test.com",
        created_at=t_snapshot - timedelta(days=50),
        status="active",
    )
    sub_active = Subscription(
        id=203,
        customer_id=203,
        plan_id=1,
        status="active",
        current_period_start=t_snapshot - timedelta(days=50),
        current_period_end=t_snapshot + timedelta(days=50),
    )

    db_session.add_all(
        [cust_future, sub_future, cust_churned, sub_churned, cust_active, sub_active]
    )
    db_session.commit()

    eligible = PanelDatasetBuilder.get_eligible_customers_at_snapshot(db_session, t_snapshot)
    assert 201 not in eligible
    assert 202 not in eligible
    assert 203 in eligible


def test_label_windows_correctness(db_session: Session) -> None:
    """Proves churn (T, T+30d] and future revenue (T, T+90d] window correctness."""
    t_snapshot = datetime(2025, 6, 1, 0, 0, 0)
    cid = 301

    # Customer
    cust = Customer(
        id=cid,
        external_id="c_label",
        name="Label User",
        email="label@test.com",
        created_at=t_snapshot - timedelta(days=30),
        status="active",
    )
    db_session.add(cust)
    db_session.flush()

    # Case A: Cancellation at T + 15d (Inside 30d window) -> churned_30d = 1
    sub_churn_inside = Subscription(
        id=301,
        customer_id=cid,
        plan_id=1,
        status="cancelled",
        current_period_start=t_snapshot - timedelta(days=30),
        current_period_end=t_snapshot + timedelta(days=30),
        cancelled_at=t_snapshot + timedelta(days=15),
    )
    db_session.add(sub_churn_inside)

    # Transactions for Revenue:
    # 1. At T -> Excluded (not strictly after T)
    txn_at_t = Transaction(
        id=301,
        customer_id=cid,
        amount_cents=1000,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_snapshot,
    )
    # 2. At T + 10d -> Included
    txn_in_1 = Transaction(
        id=302,
        customer_id=cid,
        amount_cents=5000,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_snapshot + timedelta(days=10),
    )
    # 3. At T + 89d -> Included
    txn_in_2 = Transaction(
        id=303,
        customer_id=cid,
        amount_cents=7000,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_snapshot + timedelta(days=89),
    )
    # 4. At T + 91d -> Excluded (after 90d window)
    txn_out = Transaction(
        id=304,
        customer_id=cid,
        amount_cents=20000,
        currency="USD",
        status="succeeded",
        type="payment",
        transaction_date=t_snapshot + timedelta(days=91),
    )
    # 5. Failed txn in window -> Excluded
    txn_failed = Transaction(
        id=305,
        customer_id=cid,
        amount_cents=5000,
        currency="USD",
        status="failed",
        type="payment",
        transaction_date=t_snapshot + timedelta(days=20),
    )
    db_session.add_all([txn_at_t, txn_in_1, txn_in_2, txn_out, txn_failed])
    db_session.commit()

    churn_label, rev_label = PanelDatasetBuilder.compute_labels_for_customer(
        db_session, cid, t_snapshot
    )
    assert churn_label == 1
    # 5000 + 7000 = 12000 cents
    assert rev_label == 12000.0

    # Case B: Cancellation outside 30d window (at T + 35d) -> churned_30d = 0
    sub_churn_inside.cancelled_at = t_snapshot + timedelta(days=35)
    db_session.commit()

    churn_label_out, _ = PanelDatasetBuilder.compute_labels_for_customer(
        db_session, cid, t_snapshot
    )
    assert churn_label_out == 0


def test_feature_schema_strictness() -> None:
    """Verifies RawCustomerFeatures enforces strict types, non-negativity, and extra forbidding."""
    valid_data: dict[str, Any] = {
        "tenure_days": 120,
        "monthly_revenue": 7900.0,
        "total_revenue_to_date": 31600.0,
        "transaction_count_90d": 3,
        "avg_transaction_value_90d": 7900.0,
        "days_since_last_activity": 4,
        "activity_count_30d": 15,
        "activity_count_90d": 40,
        "login_frequency_30d": 8,
        "support_ticket_count_90d": 0,
        "payment_failure_count_90d": 0,
        "engagement_score": 75.5,
        "subscription_length_days": 90,
        "plan_tier": "pro",
        "billing_cycle": "monthly",
        "acquisition_channel": "referral",
        "region": "europe",
    }
    feats = RawCustomerFeatures(**valid_data)
    assert feats.tenure_days == 120
    assert len(feats.to_row()) == len(ALL_FEATURES)
    assert isinstance(feats.compute_hash(), str)

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        RawCustomerFeatures(**{**valid_data, "unauthorized_field": 123})

    # Negative values forbidden
    with pytest.raises(ValidationError):
        RawCustomerFeatures(**{**valid_data, "tenure_days": -5})


def test_synthetic_panel_generation_determinism() -> None:
    """Verifies synthetic panel generator produces consistent, well-formed datasets."""
    df1 = generate_synthetic_panel_dataset(num_customers=50, num_snapshots=3, seed=123)
    df2 = generate_synthetic_panel_dataset(num_customers=50, num_snapshots=3, seed=123)

    assert not df1.empty
    assert len(df1) == len(df2)
    assert list(df1.columns) == list(df2.columns)
    # Test identical outputs from identical seed
    assert df1["churned_30d"].tolist() == df2["churned_30d"].tolist()
    assert df1["future_revenue_90d"].tolist() == df2["future_revenue_90d"].tolist()

    # Verify all expected columns exist
    for col in ALL_FEATURES + ["churned_30d", "future_revenue_90d"]:
        assert col in df1.columns
