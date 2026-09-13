"""Схеми відповіді для розкладу та місць."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.bus import BusClass
from app.models.seat import SeatStatus
from app.models.trip import TripStatus


class RouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    origin_city: str
    destination_city: str
    distance_km: int
    duration_minutes: int
    is_active: bool


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int
    bus_type_id: int
    bus_id: int | None
    departure_at: datetime
    arrival_at: datetime
    status: TripStatus
    base_price: Decimal


class SeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    row_index: int
    column_index: int
    status: SeatStatus


class TripSeatMapRead(BaseModel):
    """Схема салону рейсу: сітка шаблону плюс актуальний стан місць."""

    trip_id: int
    bus_class: BusClass
    row_count: int
    column_count: int
    layout: list[list[int]]
    seats: list[SeatRead]
