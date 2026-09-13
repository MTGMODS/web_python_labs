"""Місця конкретного рейсу."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.trip import Trip


class SeatStatus(enum.StrEnum):
    """Життєвий цикл місця.

    HELD — місце тимчасово заблоковане під час оформлення (поле held_until).
    Саме перехід FREE -> HELD і є критичною секцією предметної області.
    """

    FREE = "free"
    HELD = "held"
    SOLD = "sold"


seat_status_enum = Enum(
    SeatStatus,
    name="seat_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Seat(Base, TimestampMixin):
    """Місце в салоні на конкретний рейс.

    Унікальність (trip_id, number) — головна гарантія бази даних проти подвійного
    продажу одного місця незалежно від кількості екземплярів застосунку.
    """

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("trip_id", "number", name="uq_seats_trip_number"),
        Index("ix_seats_trip_status", "trip_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[str] = mapped_column(String(8), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        seat_status_enum,
        default=SeatStatus.FREE,
        nullable=False,
    )
    held_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped[Trip] = relationship(back_populates="seats")
    # Скасовані квитки на місце залишаються в історії, тому зв'язок — список.
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="seat",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Seat {self.number} trip={self.trip_id} {self.status.value}>"
