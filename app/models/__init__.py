"""Моделі предметної області.

Імпорт усіх моделей в одному місці потрібен, щоб Alembic та конфігуратор мапперів
SQLAlchemy бачили повні метадані.
"""

from app.models.bus import Bus, BusClass, BusType
from app.models.route import Route
from app.models.seat import Seat, SeatStatus
from app.models.trip import Trip, TripStatus

__all__ = [
    "Bus",
    "BusClass",
    "BusType",
    "Route",
    "Seat",
    "SeatStatus",
    "Trip",
    "TripStatus",
]
