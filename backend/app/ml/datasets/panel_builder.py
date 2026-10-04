"""Panel dataset builder constructing (customer, snapshot) panels with strict leakage controls."""

import hashlib
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.features.extractor import FeatureEngineeringService
from app.ml.features.schemas import ALL_FEATURES, FEATURE_VERSION
from app.models.customer import Customer
from app.models.subscription import Subscription
from app.models.transaction import Transaction


class PanelDatasetBuilder:
    """Builds historical (customer, snapshot) feature panels with temporal splits."""

    @classmethod
    def get_max_data_timestamp(cls, db: Session) -> datetime:
        """Finds latest event or transaction timestamp available in the database."""
        max_txn = db.execute(select(func.max(Transaction.transaction_date))).scalar()
        max_sub = db.execute(select(func.max(Subscription.created_at))).scalar()
        dates = [d for d in [max_txn, max_sub] if d is not None]
        return max(dates) if dates else datetime.utcnow()

    @classmethod
    def get_eligible_customers_at_snapshot(cls, db: Session, snapshot: datetime) -> list[int]:
        """Returns customer IDs who were active and not churned at snapshot date T."""
        stmt = (
            select(Customer.id)
            .join(Subscription, Customer.id == Subscription.customer_id)
            .where(
                Customer.created_at <= snapshot,
                Subscription.current_period_start <= snapshot,
                (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > snapshot),
            )
            .distinct()
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def compute_labels_for_customer(
        cls, db: Session, customer_id: int, snapshot: datetime
    ) -> tuple[int, float]:
        """Computes future labels strictly in (T, T+30d] for churn and (T, T+90d] for revenue."""
        # 1. Churned in (T, T + 30d]
        churn_cutoff = snapshot + timedelta(days=30)
        churn_stmt = select(func.count(Subscription.id)).where(
            Subscription.customer_id == customer_id,
            Subscription.cancelled_at > snapshot,
            Subscription.cancelled_at <= churn_cutoff,
        )
        churn_count = int(db.execute(churn_stmt).scalar() or 0)
        churned_30d = 1 if churn_count > 0 else 0

        # 2. Future revenue in (T, T + 90d]
        rev_cutoff = snapshot + timedelta(days=90)
        rev_stmt = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_date > snapshot,
            Transaction.transaction_date <= rev_cutoff,
            Transaction.status == "succeeded",
            Transaction.type == "payment",
        )
        future_revenue_90d = float(db.execute(rev_stmt).scalar() or 0.0)

        return churned_30d, future_revenue_90d

    @classmethod
    def build_panel_dataset(
        cls,
        db: Session,
        snapshot_interval_days: int = 30,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> dict[str, Any]:
        """Constructs temporal train/val/test panel dataset from database."""
        max_date = cls.get_max_data_timestamp(db)
        min_date_stmt = select(func.min(Customer.created_at))
        min_date = db.execute(min_date_stmt).scalar()

        if not min_date:
            empty_df = pd.DataFrame(
                columns=["customer_id", "snapshot_date"]
                + ALL_FEATURES
                + ["churned_30d", "future_revenue_90d"]
            )
            return {
                "train_df": empty_df,
                "val_df": empty_df,
                "test_df": empty_df,
                "dataset_version": "v1_empty",
                "feature_version": FEATURE_VERSION,
                "snapshots": [],
            }

        # Generate snapshot dates with at least 90 days of label history
        snapshots: list[datetime] = []
        curr = min_date + timedelta(days=snapshot_interval_days)
        while curr + timedelta(days=90) <= max_date:
            snapshots.append(curr)
            curr += timedelta(days=snapshot_interval_days)

        rows: list[dict[str, Any]] = []
        for snap in snapshots:
            eligible_ids = cls.get_eligible_customers_at_snapshot(db, snap)
            for cid in eligible_ids:
                feats = FeatureEngineeringService.compute_features_for_customer(db, cid, as_of=snap)
                churn_label, rev_label = cls.compute_labels_for_customer(db, cid, snap)
                row_dict: dict[str, Any] = {
                    "customer_id": cid,
                    "snapshot_date": snap.isoformat(),
                    "churned_30d": churn_label,
                    "future_revenue_90d": rev_label,
                }
                row_dict.update(feats.to_dict())
                rows.append(row_dict)

        full_df = pd.DataFrame(rows)
        if full_df.empty:
            empty_df = pd.DataFrame(
                columns=["customer_id", "snapshot_date"]
                + ALL_FEATURES
                + ["churned_30d", "future_revenue_90d"]
            )
            return {
                "train_df": empty_df,
                "val_df": empty_df,
                "test_df": empty_df,
                "dataset_version": "v1_empty",
                "feature_version": FEATURE_VERSION,
                "snapshots": [],
            }

        # Chronological temporal split by snapshot date
        n_snaps = len(snapshots)
        train_idx = int(n_snaps * train_ratio)
        val_idx = int(n_snaps * (train_ratio + val_ratio))

        train_snaps = {s.isoformat() for s in snapshots[:train_idx]}
        val_snaps = {s.isoformat() for s in snapshots[train_idx:val_idx]}
        test_snaps = {s.isoformat() for s in snapshots[val_idx:]}

        train_df = full_df[full_df["snapshot_date"].isin(train_snaps)].reset_index(drop=True)
        val_df = full_df[full_df["snapshot_date"].isin(val_snaps)].reset_index(drop=True)
        test_df = full_df[full_df["snapshot_date"].isin(test_snaps)].reset_index(drop=True)

        # Deterministic dataset version hash
        hash_input = (
            f"{FEATURE_VERSION}_{len(train_df)}_{len(val_df)}_{len(test_df)}_"
            f"{','.join(s.isoformat() for s in snapshots)}"
        )
        dataset_version = f"dset_{hashlib.sha256(hash_input.encode()).hexdigest()[:8]}"

        return {
            "train_df": train_df,
            "val_df": val_df,
            "test_df": test_df,
            "dataset_version": dataset_version,
            "feature_version": FEATURE_VERSION,
            "snapshots": [s.isoformat() for s in snapshots],
        }
