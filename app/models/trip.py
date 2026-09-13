"""Рейси (динамічний розклад)."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.bus import Bus, BusType
    from app.models.route import Route
    from app.models.seat import Seat


class TripStatus(enum.StrEnum):
    """Стан рейсу. Саме зміна цих значень і робить розклад динамічним."""

    SCHEDULED = "scheduled"
    DELAYED = "delayed"
    DEPARTED = "departed"
    CANCELLED = "cancelled"


trip_status_enum = Enum(
    TripStatus,
    name="trip_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Trip(Base, TimestampMixin):
    """Конкретний виїзд за маршрутом у визначений час."""

    __tablename__ = "trips"
    __table_args__ = (
        UniqueConstraint("route_id", "departure_at", name="uq_trips_route_departure"),
        Index("ix_trips_departure_at", "departure_at"),
        Index("ix_trips_route_departure", "route_id", "departure_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    bus_type_id: Mapped[int] = mapped_column(
        ForeignKey("bus_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bus_id: Mapped[int | None] = mapped_column(
        ForeignKey("buses.id", ondelete="SET NULL"),
        nullable=True,
    )
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        trip_status_enum,
        default=TripStatus.SCHEDULED,
        nullable=False,
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    route: Mapped[Route] = relationship(back_populates="trips")
    bus_type: Mapped[BusType] = relationship(back_populates="trips")
    bus: Mapped[Bus | None] = relationship(back_populates="trips")
    seats: Mapped[list[Seat]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Trip {self.id} route={self.route_id} at={self.departure_at:%Y-%m-%d %H:%M}>"
