"""Парк автобусів: три шаблони салону та конкретні борти."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonColumn, TimestampMixin

if TYPE_CHECKING:
    from app.models.trip import Trip


class BusClass(enum.StrEnum):
    """Класи автобусів. Клас рейсу залежить від довжини маршруту."""

    MINI = "mini"
    STANDARD = "standard"
    LARGE = "large"


bus_class_enum = Enum(
    BusClass,
    name="bus_class",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class BusType(Base, TimestampMixin):
    """Шаблон салону.

    Схема місць зберігається у полі layout як матриця: 1 — місце, 0 — прохід.
    Конкретні місця рейсу генеруються з цього шаблону, тому окремий редактор
    схеми салону не потрібен.
    """

    __tablename__ = "bus_types"
    __table_args__ = (
        CheckConstraint("seats_count > 0", name="seats_positive"),
        CheckConstraint(
            "max_distance_km IS NULL OR max_distance_km >= min_distance_km",
            name="distance_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[BusClass] = mapped_column(bus_class_enum, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_count: Mapped[int] = mapped_column(Integer, nullable=False)
    layout: Mapped[list[list[int]]] = mapped_column(JsonColumn, nullable=False)
    min_distance_km: Mapped[int] = mapped_column(Integer, nullable=False)
    max_distance_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    buses: Mapped[list[Bus]] = relationship(back_populates="bus_type")
    trips: Mapped[list[Trip]] = relationship(back_populates="bus_type")

    def __repr__(self) -> str:
        return f"<BusType {self.code.value} seats={self.seats_count}>"


class Bus(Base, TimestampMixin):
    """Конкретний автобус парку. Кількість бортів довільна, шаблонів — три."""

    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    bus_type_id: Mapped[int] = mapped_column(
        ForeignKey("bus_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bus_type: Mapped[BusType] = relationship(back_populates="buses")
    trips: Mapped[list[Trip]] = relationship(back_populates="bus")

    def __repr__(self) -> str:
        return f"<Bus {self.plate}>"
