"""Маршрути між містами."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.trip import Trip


class Route(Base, TimestampMixin):
    """Напрямок перевезення. Довжина маршруту визначає клас автобуса."""

    __tablename__ = "routes"
    __table_args__ = (
        CheckConstraint("distance_km > 0", name="distance_positive"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        Index("ix_routes_cities", "origin_city", "destination_city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    origin_city: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(64), nullable=False)
    distance_km: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    trips: Mapped[list[Trip]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Route {self.code} {self.origin_city}->{self.destination_city}>"
