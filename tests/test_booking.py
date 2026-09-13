"""Бізнес-логіка бронювання: утримання місця, оплата, скасування."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Seat, SeatStatus, Ticket, TicketStatus, Trip, TripStatus, User

AuthHeader = Callable[[User], dict[str, str]]


def _seat(session: Session, trip_id: int, number: str) -> Seat:
    return session.scalars(select(Seat).where(Seat.trip_id == trip_id, Seat.number == number)).one()


def test_hold_marks_seat_and_creates_ticket(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    response = client.post(
        f"/api/v1/trips/{trip.id}/seats/3/hold",
        headers=auth_header(passenger),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == TicketStatus.HELD.value
    assert body["seat"]["number"] == "3"
    assert body["expires_at"] is not None

    db_session.expire_all()
    assert _seat(db_session, trip.id, "3").status is SeatStatus.HELD


def test_second_passenger_cannot_hold_same_seat(
    client: TestClient,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    """Конкурентний доступ до однієї одиниці товару — ключовий сценарій області."""
    first = client.post(f"/api/v1/trips/{trip.id}/seats/4/hold", headers=auth_header(passenger))
    second = client.post(
        f"/api/v1/trips/{trip.id}/seats/4/hold",
        headers=auth_header(other_passenger),
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_hold_unknown_seat_returns_404(
    client: TestClient, trip: Trip, passenger: User, auth_header: AuthHeader
) -> None:
    response = client.post(
        f"/api/v1/trips/{trip.id}/seats/9999/hold",
        headers=auth_header(passenger),
    )

    assert response.status_code == 404


def test_hold_unknown_trip_returns_404(
    client: TestClient, passenger: User, auth_header: AuthHeader
) -> None:
    response = client.post("/api/v1/trips/987654/seats/1/hold", headers=auth_header(passenger))

    assert response.status_code == 404


def test_cancelled_trip_cannot_be_booked(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    trip.status = TripStatus.CANCELLED
    db_session.commit()

    response = client.post(f"/api/v1/trips/{trip.id}/seats/1/hold", headers=auth_header(passenger))

    assert response.status_code == 409


def test_departed_trip_cannot_be_booked(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    trip.departure_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    response = client.post(f"/api/v1/trips/{trip.id}/seats/1/hold", headers=auth_header(passenger))

    assert response.status_code == 409


def test_payment_sells_the_seat(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/5/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    response = client.post(f"/api/v1/tickets/{ticket_id}/pay", headers=auth_header(passenger))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == TicketStatus.PAID.value
    assert body["paid_at"] is not None
    assert body["seat"]["status"] == SeatStatus.SOLD.value

    db_session.expire_all()
    assert _seat(db_session, trip.id, "5").status is SeatStatus.SOLD


def test_double_payment_is_rejected(
    client: TestClient, trip: Trip, passenger: User, auth_header: AuthHeader
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/6/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    client.post(f"/api/v1/tickets/{ticket_id}/pay", headers=auth_header(passenger))
    repeat = client.post(f"/api/v1/tickets/{ticket_id}/pay", headers=auth_header(passenger))

    assert repeat.status_code == 409


def test_cancellation_returns_seat_to_sale(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/8/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    response = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=auth_header(passenger))

    assert response.status_code == 200
    assert response.json()["seat"]["status"] == SeatStatus.FREE.value

    db_session.expire_all()
    assert _seat(db_session, trip.id, "8").status is SeatStatus.FREE


def test_seat_can_be_rebooked_after_cancellation(
    client: TestClient,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    """Частковий унікальний індекс не заважає продати місце після скасування."""
    held = client.post(f"/api/v1/trips/{trip.id}/seats/9/hold", headers=auth_header(passenger))
    client.post(f"/api/v1/tickets/{held.json()['id']}/cancel", headers=auth_header(passenger))

    rebooked = client.post(
        f"/api/v1/trips/{trip.id}/seats/9/hold",
        headers=auth_header(other_passenger),
    )

    assert rebooked.status_code == 201


def test_expired_hold_frees_the_seat(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/10/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    # Імітуємо збіг терміну утримання, не чекаючи реальних хвилин.
    expired_moment = datetime.now(UTC) - timedelta(minutes=1)
    ticket = db_session.get(Ticket, ticket_id)
    assert ticket is not None
    ticket.expires_at = expired_moment
    _seat(db_session, trip.id, "10").held_until = expired_moment
    db_session.commit()

    taken_over = client.post(
        f"/api/v1/trips/{trip.id}/seats/10/hold",
        headers=auth_header(other_passenger),
    )

    assert taken_over.status_code == 201
    db_session.expire_all()
    released = db_session.get(Ticket, ticket_id)
    assert released is not None
    assert released.status is TicketStatus.CANCELLED


def test_expired_hold_cannot_be_paid(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/11/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    expired_moment = datetime.now(UTC) - timedelta(minutes=1)
    ticket = db_session.get(Ticket, ticket_id)
    assert ticket is not None
    ticket.expires_at = expired_moment
    _seat(db_session, trip.id, "11").held_until = expired_moment
    db_session.commit()

    response = client.post(f"/api/v1/tickets/{ticket_id}/pay", headers=auth_header(passenger))

    assert response.status_code == 409


def test_admin_can_cancel_any_ticket(
    client: TestClient,
    trip: Trip,
    passenger: User,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/12/hold", headers=auth_header(passenger))
    ticket_id = held.json()["id"]

    response = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json()["status"] == TicketStatus.CANCELLED.value


def test_passenger_home_summarizes_own_tickets(
    client: TestClient, trip: Trip, passenger: User, auth_header: AuthHeader
) -> None:
    client.post(f"/api/v1/trips/{trip.id}/seats/13/hold", headers=auth_header(passenger))

    response = client.get("/api/v1/me/home", headers=auth_header(passenger))

    body = response.json()
    assert body["tickets_total"] == 1
    assert body["tickets_by_status"]["held"] == 1
    assert body["available_actions"]
