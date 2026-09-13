"""Квитки: зв'язок користувача з конкретним місцем на конкретному рейсі."""

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.seat import Seat
    from app.models.trip import Trip
    from app.models.user import User


class TicketStatus(enum.StrEnum):
    """Життєвий цикл квитка, узгоджений зі станом місця.

    HELD — місце утримується до закінчення expires_at (seat.status = held).
    PAID — оплачено, місце продане (seat.status = sold).
    CANCELLED — скасовано, місце повернулося у продаж (seat.status = free).
    """

    HELD = "held"
    PAID = "paid"
    CANCELLED = "cancelled"


ticket_status_enum = Enum(
    TicketStatus,
    name="ticket_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Ticket(Base, TimestampMixin):
    """Квиток користувача.

    Частковий унікальний індекс гарантує, що в один момент часу на місце існує
    щонайбільше один нескасований квиток. Це друга, незалежна від коду захисна
    межа проти подвійного продажу місця.
    """

    __tablename__ = "tickets"
    __table_args__ = (
        Index(
            "uq_tickets_active_seat",
            "seat_id",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
        ),
        Index("ix_tickets_user_created", "user_id", "created_at"),
        Index("ix_tickets_trip_status", "trip_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        ticket_status_enum,
        default=TicketStatus.HELD,
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="tickets")
    trip: Mapped[Trip] = relationship(back_populates="tickets")
    seat: Mapped[Seat] = relationship(back_populates="tickets")

    def __repr__(self) -> str:
        return f"<Ticket {self.id} user={self.user_id} seat={self.seat_id} {self.status.value}>"
