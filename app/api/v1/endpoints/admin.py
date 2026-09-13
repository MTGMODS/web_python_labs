"""Адміністративні маршрути перевізника.

Усі маршрути захищені залежністю AdminUser, тому звичайний користувач отримує
403 Forbidden ще до виконання тіла функції.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep, require_admin
from app.models.route import Route
from app.models.ticket import Ticket
from app.models.trip import Trip
from app.models.user import User
from app.schemas.booking import (
    AdminHomeRead,
    TicketRead,
    TripCreateRequest,
    TripUpdateRequest,
)
from app.schemas.schedule import TripRead
from app.services import booking as booking_service
from app.services import schedule as schedule_service

# Перевірка ролі оголошена на рівні роутера: новий адміністративний маршрут
# неможливо випадково додати без контролю доступу.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

ADMIN_ACTIONS = [
    "POST /api/v1/admin/trips — додати рейс у розклад",
    "PATCH /api/v1/admin/trips/{trip_id} — змінити час або скасувати рейс",
    "GET /api/v1/admin/tickets — усі квитки системи",
    "POST /api/v1/tickets/{ticket_id}/cancel — скасувати будь-який квиток",
]


@router.get("/home", response_model=AdminHomeRead, summary="Домашня сторінка адміністратора")
def admin_home(admin: AdminUser, session: SessionDep) -> AdminHomeRead:
    return AdminHomeRead(
        role=admin.role,
        full_name=admin.full_name,
        users_total=session.scalar(select(func.count(User.id))) or 0,
        routes_total=session.scalar(select(func.count(Route.id))) or 0,
        trips_total=session.scalar(select(func.count(Trip.id))) or 0,
        tickets_by_status=booking_service.count_tickets_by_status(session),
        available_actions=ADMIN_ACTIONS,
    )


@router.get("/tickets", response_model=list[TicketRead], summary="Усі квитки системи")
def all_tickets(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Ticket]:
    return booking_service.list_all_tickets(session, limit=limit)


@router.post(
    "/trips",
    response_model=TripRead,
    status_code=status.HTTP_201_CREATED,
    summary="Додати рейс у розклад",
)
def create_trip(payload: TripCreateRequest, session: SessionDep) -> Trip:
    return schedule_service.create_trip(
        session,
        route_id=payload.route_id,
        departure_at=payload.departure_at,
        base_price=payload.base_price,
        bus_id=payload.bus_id,
    )


@router.patch("/trips/{trip_id}", response_model=TripRead, summary="Змінити рейс")
def update_trip(
    trip_id: int,
    payload: TripUpdateRequest,
    session: SessionDep,
) -> Trip:
    return schedule_service.update_trip(
        session,
        trip_id,
        departure_at=payload.departure_at,
        status=payload.status,
    )
