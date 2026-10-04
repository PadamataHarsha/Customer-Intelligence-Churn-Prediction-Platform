"""Feature engineering service computing snapshot features honoring leakage rules."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.ml.features.schemas import FEATURE_VERSION, RawCustomerFeatures
from app.models.activity import CustomerActivity
from app.models.customer import Customer, CustomerProfile
from app.models.event import CustomerEvent
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.transaction import Transaction


class FeatureEngineeringService:
    """Computes features as of snapshot date T with absolute leakage controls."""

    FEATURE_VERSION = FEATURE_VERSION

    @classmethod
    def compute_features_for_customer(
        cls, db: Session, customer_id: int, as_of: datetime
    ) -> RawCustomerFeatures:
        """Computes all raw features for customer strictly using data timestamped <= as_of."""
        # 1. Customer & Profile
        customer_stmt = (
            select(Customer, CustomerProfile)
            .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
            .where(Customer.id == customer_id)
        )
        row = db.execute(customer_stmt).first()
        if not row:
            raise NotFoundException(f"Customer {customer_id} not found", code="CUSTOMER_NOT_FOUND")

        customer, profile = row
        if customer.created_at > as_of:
            msg = (
                f"Customer {customer_id} was created at {customer.created_at}, "
                f"which is after as_of {as_of}"
            )
            raise ValueError(msg)

        tenure_days = max(0, (as_of - customer.created_at).days)
        acquisition_channel = profile.acquisition_channel if profile else "organic_search"
        region = profile.region if profile else "north_america"

        # 2. Active Subscription & Plan as of T
        # Valid if started <= as_of and (cancelled_at is NULL or cancelled_at > as_of)
        sub_stmt = (
            select(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .where(
                Subscription.customer_id == customer_id,
                Subscription.current_period_start <= as_of,
                (Subscription.cancelled_at.is_(None)) | (Subscription.cancelled_at > as_of),
            )
            .order_by(Subscription.current_period_start.desc())
        )
        sub_row = db.execute(sub_stmt).first()

        if sub_row:
            sub, plan = sub_row
            plan_tier = plan.tier
            billing_cycle = plan.billing_cycle
            monthly_revenue = (
                float(plan.price_cents) / 12.0
                if plan.billing_cycle == "annual"
                else float(plan.price_cents)
            )
            subscription_length_days = max(0, (as_of - sub.current_period_start).days)
        else:
            plan_tier = "basic"
            billing_cycle = "monthly"
            monthly_revenue = 0.0
            subscription_length_days = 0

        # 3. Transactions <= as_of
        cutoff_90d = as_of - timedelta(days=90)

        # Total revenue to date
        tot_rev_stmt = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_date <= as_of,
            Transaction.status == "succeeded",
            Transaction.type == "payment",
        )
        total_revenue_to_date = float(db.execute(tot_rev_stmt).scalar() or 0.0)

        # 90d Transactions
        txn_90d_stmt = select(
            func.count(Transaction.id),
            func.coalesce(func.avg(Transaction.amount_cents), 0.0),
        ).where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_date > cutoff_90d,
            Transaction.transaction_date <= as_of,
            Transaction.status == "succeeded",
            Transaction.type == "payment",
        )
        t_count, t_avg = db.execute(txn_90d_stmt).one()
        transaction_count_90d = int(t_count)
        avg_transaction_value_90d = round(float(t_avg), 2)

        # Failed transactions 90d
        failed_txn_stmt = select(func.count(Transaction.id)).where(
            Transaction.customer_id == customer_id,
            Transaction.transaction_date > cutoff_90d,
            Transaction.transaction_date <= as_of,
            Transaction.status == "failed",
        )
        failed_txns_90d = int(db.execute(failed_txn_stmt).scalar() or 0)

        # 4. Activity <= as_of
        cutoff_30d = as_of - timedelta(days=30)

        last_act_stmt = select(func.max(CustomerActivity.timestamp)).where(
            CustomerActivity.customer_id == customer_id,
            CustomerActivity.timestamp <= as_of,
        )
        last_act_dt = db.execute(last_act_stmt).scalar()
        if last_act_dt:
            days_since_last_activity = max(0, (as_of - last_act_dt).days)
        else:
            days_since_last_activity = tenure_days

        # Activity count 30d
        act_30d_stmt = select(func.coalesce(func.sum(CustomerActivity.activity_count), 0)).where(
            CustomerActivity.customer_id == customer_id,
            CustomerActivity.timestamp > cutoff_30d,
            CustomerActivity.timestamp <= as_of,
        )
        activity_count_30d = int(db.execute(act_30d_stmt).scalar() or 0)

        # Activity count 90d
        act_90d_stmt = select(func.coalesce(func.sum(CustomerActivity.activity_count), 0)).where(
            CustomerActivity.customer_id == customer_id,
            CustomerActivity.timestamp > cutoff_90d,
            CustomerActivity.timestamp <= as_of,
        )
        activity_count_90d = int(db.execute(act_90d_stmt).scalar() or 0)

        # Login frequency 30d
        login_30d_stmt = select(func.count(CustomerActivity.id)).where(
            CustomerActivity.customer_id == customer_id,
            CustomerActivity.timestamp > cutoff_30d,
            CustomerActivity.timestamp <= as_of,
            CustomerActivity.activity_type.in_(["login", "session_start"]),
        )
        login_frequency_30d = int(db.execute(login_30d_stmt).scalar() or 0)

        # 5. Events <= as_of
        ticket_stmt = select(func.count(CustomerEvent.id)).where(
            CustomerEvent.customer_id == customer_id,
            CustomerEvent.timestamp > cutoff_90d,
            CustomerEvent.timestamp <= as_of,
            CustomerEvent.event_type.in_(["support_ticket", "ticket_created", "ticket_opened"]),
        )
        support_ticket_count_90d = int(db.execute(ticket_stmt).scalar() or 0)

        payment_fail_event_stmt = select(func.count(CustomerEvent.id)).where(
            CustomerEvent.customer_id == customer_id,
            CustomerEvent.timestamp > cutoff_90d,
            CustomerEvent.timestamp <= as_of,
            CustomerEvent.event_type.in_(["payment_failed", "billing_failure", "payment_failure"]),
        )
        payment_fail_events_90d = int(db.execute(payment_fail_event_stmt).scalar() or 0)
        payment_failure_count_90d = failed_txns_90d + payment_fail_events_90d

        # 6. Engagement score
        engagement_score = cls.calculate_engagement_score(
            activity_count_30d=activity_count_30d,
            login_frequency_30d=login_frequency_30d,
            days_since_last_activity=days_since_last_activity,
        )

        return RawCustomerFeatures(
            tenure_days=tenure_days,
            monthly_revenue=round(monthly_revenue, 2),
            total_revenue_to_date=round(total_revenue_to_date, 2),
            transaction_count_90d=transaction_count_90d,
            avg_transaction_value_90d=avg_transaction_value_90d,
            days_since_last_activity=days_since_last_activity,
            activity_count_30d=activity_count_30d,
            activity_count_90d=activity_count_90d,
            login_frequency_30d=login_frequency_30d,
            support_ticket_count_90d=support_ticket_count_90d,
            payment_failure_count_90d=payment_failure_count_90d,
            engagement_score=engagement_score,
            subscription_length_days=subscription_length_days,
            plan_tier=plan_tier,
            billing_cycle=billing_cycle,
            acquisition_channel=acquisition_channel,
            region=region,
        )

    @staticmethod
    def calculate_engagement_score(
        activity_count_30d: int, login_frequency_30d: int, days_since_last_activity: int
    ) -> float:
        """Deterministic pure engagement score calculation (0 - 100)."""
        base = 30.0
        act_pts = min(40.0, activity_count_30d * 2.0)
        login_pts = min(30.0, login_frequency_30d * 5.0)
        recency_penalty = min(50.0, days_since_last_activity * 1.5)
        raw_score = base + act_pts + login_pts - recency_penalty
        return round(max(0.0, min(100.0, raw_score)), 2)
