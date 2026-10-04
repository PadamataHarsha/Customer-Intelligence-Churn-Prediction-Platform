"""Customer lifecycle business logic service."""

import uuid
from typing import Literal

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.user import User
from app.repositories.activity_repo import ActivityRepository
from app.repositories.audit_repo import AuditLogRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.event_repo import EventRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.activity import CustomerActivityResponse
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.event import CustomerEventResponse
from app.schemas.subscription import SubscriptionResponse
from app.schemas.transaction import TransactionResponse


class CustomerService:
    """Service handling customer queries, mutations, and sub-resource retrieval."""

    @staticmethod
    def get_customer(db: Session, customer_id: int) -> CustomerResponse:
        customer = CustomerRepository.get_by_id(db, customer_id)
        if not customer:
            raise NotFoundException(
                f"Customer with ID {customer_id} not found", code="CUSTOMER_NOT_FOUND"
            )
        return CustomerResponse.model_validate(customer)

    @staticmethod
    def list_customers(
        db: Session,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[CustomerResponse]:
        skip = (page - 1) * page_size
        customers, total = CustomerRepository.list_customers(
            db=db,
            status=status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=page_size,
        )
        items = [CustomerResponse.model_validate(c) for c in customers]
        return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)

    @staticmethod
    def create_customer(
        db: Session,
        payload: CustomerCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> CustomerResponse:
        existing = CustomerRepository.get_by_email(db, payload.email)
        if existing:
            raise ConflictException(
                f"Customer with email '{payload.email}' already exists",
                code="CUSTOMER_EMAIL_EXISTS",
            )

        external_id = f"cust_{uuid.uuid4().hex[:8]}"
        customer = CustomerRepository.create(
            db=db,
            external_id=external_id,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            company=payload.company,
            status=payload.status,
            profile_data=payload.profile.model_dump(),
        )

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="CUSTOMER_CREATED",
            entity_type="customer",
            entity_id=str(customer.id),
            details={"email": customer.email, "name": customer.name},
            ip_address=ip_address,
        )

        return CustomerResponse.model_validate(customer)

    @staticmethod
    def update_customer(
        db: Session,
        customer_id: int,
        payload: CustomerUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> CustomerResponse:
        customer = CustomerRepository.get_by_id(db, customer_id)
        if not customer:
            raise NotFoundException(
                f"Customer with ID {customer_id} not found", code="CUSTOMER_NOT_FOUND"
            )

        changes: dict[str, str] = {}
        if payload.name is not None:
            customer.name = payload.name
            changes["name"] = payload.name
        if payload.email is not None and payload.email.lower() != customer.email:
            existing = CustomerRepository.get_by_email(db, payload.email)
            if existing:
                raise ConflictException(
                    f"Customer with email '{payload.email}' already exists",
                    code="CUSTOMER_EMAIL_EXISTS",
                )
            customer.email = payload.email.lower()
            changes["email"] = payload.email.lower()
        if payload.phone is not None:
            customer.phone = payload.phone
            changes["phone"] = payload.phone
        if payload.company is not None:
            customer.company = payload.company
            changes["company"] = payload.company
        if payload.status is not None:
            customer.status = payload.status
            changes["status"] = payload.status

        if payload.profile is not None and customer.profile:
            prof = payload.profile
            if prof.acquisition_channel is not None:
                customer.profile.acquisition_channel = prof.acquisition_channel
            if prof.region is not None:
                customer.profile.region = prof.region
            if prof.industry is not None:
                customer.profile.industry = prof.industry
            if prof.company_size is not None:
                customer.profile.company_size = prof.company_size
            if prof.metadata_json is not None:
                customer.profile.metadata_json = prof.metadata_json

        CustomerRepository.update(db, customer)

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="CUSTOMER_UPDATED",
            entity_type="customer",
            entity_id=str(customer.id),
            details=changes,
            ip_address=ip_address,
        )

        return CustomerResponse.model_validate(customer)

    @staticmethod
    def delete_customer(
        db: Session,
        customer_id: int,
        current_user: User,
        ip_address: str | None = None,
    ) -> None:
        customer = CustomerRepository.get_by_id(db, customer_id)
        if not customer:
            raise NotFoundException(
                f"Customer with ID {customer_id} not found", code="CUSTOMER_NOT_FOUND"
            )

        CustomerRepository.delete(db, customer)

        AuditLogRepository.log(
            db=db,
            user_id=current_user.id,
            action="CUSTOMER_DELETED",
            entity_type="customer",
            entity_id=str(customer_id),
            details={"email": customer.email},
            ip_address=ip_address,
        )

    @staticmethod
    def get_activity(
        db: Session, customer_id: int, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[CustomerActivityResponse]:
        CustomerService.get_customer(db, customer_id)
        skip = (page - 1) * page_size
        items, total = ActivityRepository.list_by_customer(
            db, customer_id, skip=skip, limit=page_size
        )
        res_items = [CustomerActivityResponse.model_validate(a) for a in items]
        return PaginatedResponse.create(
            items=res_items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    def get_events(
        db: Session, customer_id: int, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[CustomerEventResponse]:
        CustomerService.get_customer(db, customer_id)
        skip = (page - 1) * page_size
        items, total = EventRepository.list_by_customer(db, customer_id, skip=skip, limit=page_size)
        res_items = [CustomerEventResponse.model_validate(e) for e in items]
        return PaginatedResponse.create(
            items=res_items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    def get_subscriptions(
        db: Session, customer_id: int, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[SubscriptionResponse]:
        CustomerService.get_customer(db, customer_id)
        skip = (page - 1) * page_size
        items, total = SubscriptionRepository.list_by_customer(
            db, customer_id, skip=skip, limit=page_size
        )
        res_items = [SubscriptionResponse.model_validate(s) for s in items]
        return PaginatedResponse.create(
            items=res_items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    def get_transactions(
        db: Session, customer_id: int, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[TransactionResponse]:
        CustomerService.get_customer(db, customer_id)
        skip = (page - 1) * page_size
        items, total = TransactionRepository.list_transactions(
            db, customer_id=customer_id, skip=skip, limit=page_size
        )
        res_items = [TransactionResponse.model_validate(t) for t in items]
        return PaginatedResponse.create(
            items=res_items, total=total, page=page, page_size=page_size
        )
