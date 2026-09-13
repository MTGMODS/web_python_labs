"""Довідник парку автобусів."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models.bus import BusType
from app.schemas.fleet import BusTypeRead

router = APIRouter(prefix="/bus-types", tags=["fleet"])


@router.get("", response_model=list[BusTypeRead], summary="Три шаблони салону")
def list_bus_types(session: SessionDep) -> list[BusType]:
    """Довідник майже не змінюється, тому в наступній роботі піде під кешування."""
    stmt = select(BusType).order_by(BusType.min_distance_km)
    return list(session.scalars(stmt))
