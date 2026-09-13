"""Маршрути, розклад рейсів та схема місць."""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models.route import Route
from app.models.seat import Seat
from app.models.trip import Trip
from app.schemas.schedule import RouteRead, SeatRead, TripRead, TripSeatMapRead

router = APIRouter(tags=["schedule"])


@router.get("/routes", response_model=list[RouteRead], summary="Активні напрямки")
def list_routes(session: SessionDep) -> list[Route]:
    stmt = select(Route).where(Route.is_active.is_(True)).order_by(Route.code)
    return list(session.scalars(stmt))


@router.get("/trips", response_model=list[TripRead], summary="Пошук рейсів")
def list_trips(
    session: SessionDep,
    route_id: int | None = Query(default=None, description="Фільтр за маршрутом"),
    departure_date: date | None = Query(default=None, description="Дата виїзду (UTC)"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Trip]:
    """Найгарячіший запит системи: пік припадає на відкриття продажів.

    Фільтр за датою навмисно зроблений діапазоном, а не функцією над колонкою,
    щоб запит використовував індекс ix_trips_route_departure.
    """
    stmt = select(Trip)

    if route_id is not None:
        stmt = stmt.where(Trip.route_id == route_id)

    if departure_date is not None:
        day_start = datetime.combine(departure_date, time.min, tzinfo=UTC)
        stmt = stmt.where(
            Trip.departure_at >= day_start,
            Trip.departure_at < day_start + timedelta(days=1),
        )

    stmt = stmt.order_by(Trip.departure_at).limit(limit)
    return list(session.scalars(stmt))


@router.get(
    "/trips/{trip_id}/seats",
    response_model=TripSeatMapRead,
    summary="Схема салону рейсу зі станом місць",
)
def get_trip_seat_map(trip_id: int, session: SessionDep) -> TripSeatMapRead:
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Рейс не знайдено",
        )

    seats_stmt = select(Seat).where(Seat.trip_id == trip_id).order_by(Seat.id)
    seats = list(session.scalars(seats_stmt))

    return TripSeatMapRead(
        trip_id=trip.id,
        bus_class=trip.bus_type.code,
        row_count=trip.bus_type.row_count,
        column_count=trip.bus_type.column_count,
        layout=trip.bus_type.layout,
        seats=[SeatRead.model_validate(seat) for seat in seats],
    )
