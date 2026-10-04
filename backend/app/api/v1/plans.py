"""Plans API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.plan import PlanResponse
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get(
    "",
    response_model=list[PlanResponse],
    summary="List available subscription plans",
)
def list_plans(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PlanResponse]:
    """Retrieves all active subscription plans."""
    return PlanService.list_plans(db=db, active_only=True)
