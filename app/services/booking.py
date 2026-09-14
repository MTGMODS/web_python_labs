"""Бронювання місць — критичний сценарій предметної області.

Арбітром конкуренції за місце є база даних, а не застосунок: рядок місця
блокується через SELECT ... FOR UPDATE, тому паралельні запити на одне й те саме
місце обслуговуються послідовно незалежно від кількості екземплярів застосунку.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.trip import Trip, TripStatus
from app.models.user import User
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)

ACTIVE_TICKET_STATUSES = (TicketStatus.HELD, TicketStatus.PAID)


def _now() -> datetime:
    return datetime.now(UTC)


def _release_if_expired(session: Session, seat: Seat, moment: datetime) -> None:
    """Повернути у продаж місце, строк утримання якого вичерпано.

    Перевірка виконується «ліниво», у момент звернення до місця. Фоновий воркер
    для масового прибирання протермінованих утримань — тема наступних робіт.
    """
    if seat.status is not SeatStatus.HELD:
        return
    if seat.held_until is None or seat.held_until > moment:
        return

    stale_ticket = session.scalar(
        select(Ticket).where(Ticket.seat_id == seat.id, Ticket.status == TicketStatus.HELD)
    )
    if stale_ticket is not None:
        stale_ticket.status = TicketStatus.CANCELLED

    seat.status = SeatStatus.FREE
    seat.held_until = None


def _tickets_query() -> Select[tuple[Ticket]]:
    return select(Ticket).options(
        selectinload(Ticket.seat),
        selectinload(Ticket.user),
        selectinload(Ticket.trip).selectinload(Trip.route),
    )


def _get_ticket_for_actor(session: Session, actor: User, ticket_id: int) -> Ticket:
    """Знайти квиток із перевіркою належності.

    Пасажир працює лише зі своїми квитками, адміністратор — з будь-якими.
    Спроба звернутися до чужого квитка дає 403, а не 404: код відповіді
    відповідає вимогам розмежування прав.
    """
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Квиток не знайдено")

    if not actor.is_admin and ticket.user_id != actor.id:
        raise PermissionDeniedError("Квиток належить іншому користувачу")

    return ticket


def hold_seat(session: Session, actor: User, trip_id: int, seat_number: str) -> Ticket:
    """Заблокувати місце за користувачем на обмежений час."""
    moment = _now()

    trip = session.get(Trip, trip_id)
    if trip is None:
        raise NotFoundError("Рейс не знайдено")
    if trip.status is not TripStatus.SCHEDULED:
        raise ConflictError("Рейс недоступний для продажу")
    if trip.departure_at <= moment:
        raise ConflictError("Рейс уже вирушив")

    # Критична секція: до COMMIT цей рядок недоступний іншим транзакціям.
    seat = session.scalars(
        select(Seat).where(Seat.trip_id == trip_id, Seat.number == seat_number).with_for_update()
    ).one_or_none()
    if seat is None:
        raise NotFoundError("Місце не знайдено")

    _release_if_expired(session, seat, moment)

    if seat.status is not SeatStatus.FREE:
        raise ConflictError("Місце вже зайняте")

    expires_at = moment + timedelta(minutes=settings.seat_hold_minutes)
    seat.status = SeatStatus.HELD
    seat.held_until = expires_at

    ticket = Ticket(
        user_id=actor.id,
        trip_id=trip.id,
        seat_id=seat.id,
        status=TicketStatus.HELD,
        price=trip.base_price,
        expires_at=expires_at,
    )
    session.add(ticket)

    try:
        session.commit()
    except IntegrityError as exc:
        # Спрацював частковий унікальний індекс uq_tickets_active_seat.
        session.rollback()
        raise ConflictError("Місце вже зайняте") from exc

    session.refresh(ticket)
    return ticket


def pay_ticket(session: Session, actor: User, ticket_id: int) -> Ticket:
    """Підтвердити оплату: місце переходить із утримання у продане."""
    moment = _now()
    ticket = _get_ticket_for_actor(session, actor, ticket_id)

    if ticket.status is TicketStatus.PAID:
        raise ConflictError("Квиток уже оплачений")
    if ticket.status is TicketStatus.CANCELLED:
        raise ConflictError("Квиток скасований")

    seat = session.scalars(select(Seat).where(Seat.id == ticket.seat_id).with_for_update()).one()

    if ticket.expires_at is not None and ticket.expires_at <= moment:
        _release_if_expired(session, seat, moment)
        session.commit()
        raise ConflictError("Час утримання місця вичерпано, оформіть бронювання заново")

    ticket.status = TicketStatus.PAID
    ticket.paid_at = moment
    ticket.expires_at = None
    seat.status = SeatStatus.SOLD
    seat.held_until = None

    session.commit()
    session.refresh(ticket)
    return ticket


def cancel_ticket(session: Session, actor: User, ticket_id: int) -> Ticket:
    """Скасувати квиток: місце повертається у продаж."""
    ticket = _get_ticket_for_actor(session, actor, ticket_id)

    if ticket.status is TicketStatus.CANCELLED:
        raise ConflictError("Квиток уже скасований")

    seat = session.scalars(select(Seat).where(Seat.id == ticket.seat_id).with_for_update()).one()

    ticket.status = TicketStatus.CANCELLED
    ticket.expires_at = None
    seat.status = SeatStatus.FREE
    seat.held_until = None

    session.commit()
    session.refresh(ticket)
    return ticket


def list_user_tickets(session: Session, actor: User) -> list[Ticket]:
    """Квитки лише поточного користувача."""
    stmt = _tickets_query().where(Ticket.user_id == actor.id).order_by(Ticket.created_at.desc())
    return list(session.scalars(stmt))


def list_all_tickets(session: Session, limit: int = 100) -> list[Ticket]:
    """Усі квитки системи. Використовується лише адміністративними маршрутами."""
    stmt = _tickets_query().order_by(Ticket.created_at.desc()).limit(limit)
    return list(session.scalars(stmt))


def count_tickets_by_status(session: Session, trip_id: int | None = None) -> dict[str, int]:
    """Зведення для домашніх сторінок.

    Підрахунок робить база (GROUP BY), а не Python: кількість квитків зростає
    лінійно з навантаженням, і вигружати їх у пам'ять заради counter не можна.
    """
    stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    if trip_id is not None:
        stmt = stmt.where(Ticket.trip_id == trip_id)

    counters = dict.fromkeys((item.value for item in TicketStatus), 0)
    for ticket_status, total in session.execute(stmt):
        counters[ticket_status.value] = total
    return counters
