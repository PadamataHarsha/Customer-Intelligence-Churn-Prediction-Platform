"""Customer and CustomerProfile database repository."""

from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer, CustomerProfile


class CustomerRepository:
    """Repository handling persistence for Customers and Profiles."""

    ALLOWED_SORT_FIELDS = {
        "id": Customer.id,
        "name": Customer.name,
        "email": Customer.email,
        "status": Customer.status,
        "created_at": Customer.created_at,
    }

    @classmethod
    def get_by_id(cls, db: Session, customer_id: int) -> Customer | None:
        stmt = (
            select(Customer).options(joinedload(Customer.profile)).where(Customer.id == customer_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @classmethod
    def get_by_email(cls, db: Session, email: str) -> Customer | None:
        stmt = (
            select(Customer)
            .options(joinedload(Customer.profile))
            .where(Customer.email == email.lower())
        )
        return db.execute(stmt).scalar_one_or_none()

    @classmethod
    def list_customers(
        cls,
        db: Session,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        """Lists customers with filtering, searching, allow-listed sorting, and total count.
        Eagerly loads Customer.profile in a single JOIN to guarantee zero N+1 queries.
        """
        stmt = select(Customer).options(joinedload(Customer.profile))
        count_stmt = select(func.count(Customer.id))

        if status:
            stmt = stmt.where(Customer.status == status)
            count_stmt = count_stmt.where(Customer.status == status)

        if search:
            search_pattern = f"%{search.lower()}%"
            filter_expr = or_(
                func.lower(Customer.name).like(search_pattern),
                func.lower(Customer.email).like(search_pattern),
                func.lower(Customer.company).like(search_pattern),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total = db.execute(count_stmt).scalar() or 0

        # Sort field allow-listing
        sort_column = cls.ALLOWED_SORT_FIELDS.get(sort_by, Customer.created_at)
        if sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        stmt = stmt.offset(skip).limit(limit)
        customers = list(db.execute(stmt).scalars().unique().all())

        return customers, total

    @classmethod
    def create(
        cls,
        db: Session,
        external_id: str,
        name: str,
        email: str,
        phone: str | None,
        company: str | None,
        status: str,
        profile_data: dict[str, Any],
    ) -> Customer:
        customer = Customer(
            external_id=external_id,
            name=name,
            email=email.lower(),
            phone=phone,
            company=company,
            status=status,
        )
        db.add(customer)
        db.flush()

        profile = CustomerProfile(
            customer_id=customer.id,
            acquisition_channel=profile_data["acquisition_channel"],
            region=profile_data["region"],
            industry=profile_data.get("industry"),
            company_size=profile_data.get("company_size"),
            metadata_json=profile_data.get("metadata_json", "{}"),
        )
        db.add(profile)
        db.commit()
        db.refresh(customer)
        return customer

    @classmethod
    def update(cls, db: Session, customer: Customer) -> Customer:
        db.commit()
        db.refresh(customer)
        return customer

    @classmethod
    def delete(cls, db: Session, customer: Customer) -> None:
        db.delete(customer)
        db.commit()
