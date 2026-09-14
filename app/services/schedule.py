"""Керування розкладом — операції адміністратора перевізника."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.fleet import build_seat_map, suggest_bus_class
from app.models.bus import Bus, BusType
from app.models.route import Route
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.trip import Trip, TripStatus
from app.services.booking import ACTIVE_TICKET_STATUSES
from app.services.exceptions import ConflictError, NotFoundError


def list_routes(session: Session, *, active_only: bool = True) -> list[Route]:
    stmt = select(Route).order_by(Route.origin_city, Route.destination_city)
    if active_only:
        stmt = stmt.where(Route.is_active.is_(True))
    return list(session.scalars(stmt))


def list_trips(
    session: Session,
    *,
    route_id: int | None = None,
    departure_date: date | None = None,
    limit: int = 50,
) -> list[Trip]:
    """Пошук рейсів для сайту й API: маршрут і дата під індекс, без функцій над колонкою."""
    stmt = (
        select(Trip)
        .options(selectinload(Trip.route), selectinload(Trip.bus_type))
        .order_by(Trip.departure_at)
        .limit(limit)
    )
    if route_id is not None:
        stmt = stmt.where(Trip.route_id == route_id)
    if departure_date is not None:
        day_start = datetime.combine(departure_date, time.min, tzinfo=UTC)
        stmt = stmt.where(
            Trip.departure_at >= day_start,
            Trip.departure_at < day_start + timedelta(days=1),
        )
    return list(session.scalars(stmt))


def get_trip(session: Session, trip_id: int) -> Trip:
    trip = session.scalar(
        select(Trip)
        .options(selectinload(Trip.route), selectinload(Trip.bus_type), selectinload(Trip.seats))
        .where(Trip.id == trip_id)
    )
    if trip is None:
        raise NotFoundError("Рейс не знайдено")
    return trip


def free_seat_counts(session: Session, trip_ids: list[int]) -> dict[int, int]:
    if not trip_ids:
        return {}
    rows = session.execute(
        select(Seat.trip_id, func.count(Seat.id))
        .where(Seat.trip_id.in_(trip_ids), Seat.status == SeatStatus.FREE)
        .group_by(Seat.trip_id)
    ).all()
    return dict(rows)


def create_trip(
    session: Session,
    *,
    route_id: int,
    departure_at: datetime,
    base_price: Decimal | None = None,
    bus_id: int | None = None,
) -> Trip:
    """Додати рейс у розклад разом зі згенерованими місцями.

    Клас автобуса не вказується вручну: він визначається довжиною маршруту, щоб
    дані не могли розійтися з правилом предметної області.
    """
    route = session.get(Route, route_id)
    if route is None:
        raise NotFoundError("Маршрут не знайдено")
    if not route.is_active:
        raise ConflictError("Маршрут неактивний")

    bus_class = suggest_bus_class(route.distance_km)
    bus_type = session.scalar(select(BusType).where(BusType.code == bus_class))
    if bus_type is None:
        raise NotFoundError(f"Шаблон салону {bus_class.value} відсутній у довіднику")

    if bus_id is not None:
        bus = session.get(Bus, bus_id)
        if bus is None:
            raise NotFoundError("Автобус не знайдено")
        if bus.bus_type_id != bus_type.id:
            raise ConflictError("Клас автобуса не відповідає довжині маршруту")

    trip = Trip(
        route_id=route.id,
        bus_type_id=bus_type.id,
        bus_id=bus_id,
        departure_at=departure_at,
        arrival_at=departure_at + timedelta(minutes=route.duration_minutes),
        status=TripStatus.SCHEDULED,
        base_price=base_price if base_price is not None else Decimal("500.00"),
    )
    session.add(trip)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Рейс за цим маршрутом на вказаний час уже існує") from exc

    session.add_all(
        Seat(
            trip_id=trip.id,
            number=position.number,
            row_index=position.row_index,
            column_index=position.column_index,
        )
        for position in build_seat_map(bus_type.layout)
    )

    session.commit()
    session.refresh(trip)
    return trip


def update_trip(
    session: Session,
    trip_id: int,
    *,
    departure_at: datetime | None = None,
    status: TripStatus | None = None,
) -> Trip:
    """Змінити час або стан рейсу — це і є динамічність розкладу."""
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError("Рейс не знайдено")

    if departure_at is not None:
        duration = trip.arrival_at - trip.departure_at
        trip.departure_at = departure_at
        trip.arrival_at = departure_at + duration

    if status is not None and status is not trip.status:
        trip.status = status
        if status is TripStatus.CANCELLED:
            _release_trip_seats(session, trip)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Рейс за цим маршрутом на вказаний час уже існує") from exc

    session.refresh(trip)
    return trip


def _release_trip_seats(session: Session, trip: Trip) -> None:
    """Скасування рейсу скасовує всі активні квитки та звільняє місця."""
    active_tickets = session.scalars(
        select(Ticket).where(
            Ticket.trip_id == trip.id,
            Ticket.status.in_(ACTIVE_TICKET_STATUSES),
        )
    ).all()

    for ticket in active_tickets:
        ticket.status = TicketStatus.CANCELLED
        ticket.expires_at = None

    seats = session.scalars(select(Seat).where(Seat.trip_id == trip.id).with_for_update()).all()
    for seat in seats:
        seat.status = SeatStatus.FREE
        seat.held_until = None
