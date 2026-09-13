"""Схеми відповіді для парку автобусів."""

from pydantic import BaseModel, ConfigDict

from app.models.bus import BusClass


class BusTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: BusClass
    title: str
    row_count: int
    column_count: int
    seats_count: int
    layout: list[list[int]]
    min_distance_km: int
    max_distance_km: int | None


class BusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    bus_type_id: int
    is_active: bool
