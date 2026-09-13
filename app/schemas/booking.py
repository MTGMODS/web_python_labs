"""Схеми квитків, керування розкладом та домашніх сторінок ролей."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import TicketStatus
from app.models.trip import TripStatus
from app.models.user import UserRole
from app.schemas.schedule import SeatRead


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    trip_id: int
    status: TicketStatus
    price: Decimal
    expires_at: datetime | None
    paid_at: datetime | None
    seat: SeatRead


class TripCreateRequest(BaseModel):
    route_id: int
    departure_at: datetime
    base_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    bus_id: int | None = None


class TripUpdateRequest(BaseModel):
    """Часткове оновлення рейсу: час, стан або обидва поля."""

    departure_at: datetime | None = None
    status: TripStatus | None = None


class PassengerHomeRead(BaseModel):
    """Домашня сторінка-заглушка звичайного користувача."""

    role: UserRole
    full_name: str
    tickets_total: int
    tickets_by_status: dict[str, int]
    available_actions: list[str]


class AdminHomeRead(BaseModel):
    """Домашня сторінка-заглушка адміністратора."""

    role: UserRole
    full_name: str
    users_total: int
    routes_total: int
    trips_total: int
    tickets_by_status: dict[str, int]
    available_actions: list[str]
