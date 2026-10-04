"""Plan business logic service."""

from sqlalchemy.orm import Session

from app.repositories.plan_repo import PlanRepository
from app.schemas.plan import PlanResponse


class PlanService:
    """Service handling plans."""

    @staticmethod
    def list_plans(db: Session, active_only: bool = True) -> list[PlanResponse]:
        plans = PlanRepository.list_all(db, active_only=active_only)
        return [PlanResponse.model_validate(p) for p in plans]
