"""Керування динамічним розкладом адміністратором."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BusType, Route, SeatStatus, TicketStatus, Trip, TripStatus, User
from app.models.bus import BusClass

AuthHeader = Callable[[User], dict[str, str]]

ADMIN_TRIPS_URL = "/api/v1/admin/trips"


def _departure(days: int = 5, hour: int = 9) -> str:
    moment = datetime.now(UTC) + timedelta(days=days)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def test_admin_creates_trip_with_class_by_distance(
    client: TestClient,
    db_session: Session,
    bus_types: list[BusType],
    long_route: Route,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    """Клас автобуса не передається у запиті — його визначає довжина маршруту."""
    del bus_types

    response = client.post(
        ADMIN_TRIPS_URL,
        headers=auth_header(admin),
        json={
            "route_id": long_route.id,
            "departure_at": _departure(),
            "base_price": "820.00",
        },
    )

    assert response.status_code == 201
    created = response.json()

    trip = db_session.get(Trip, created["id"])
    assert trip is not None
    assert trip.bus_type.code is BusClass.LARGE
    assert len(trip.seats) == trip.bus_type.seats_count


def test_created_trip_arrival_follows_route_duration(
    client: TestClient,
    db_session: Session,
    bus_types: list[BusType],
    long_route: Route,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    del bus_types

    response = client.post(
        ADMIN_TRIPS_URL,
        headers=auth_header(admin),
        json={
            "route_id": long_route.id,
            "departure_at": _departure(),
            "base_price": "820.00",
        },
    )

    trip = db_session.get(Trip, response.json()["id"])
    assert trip is not None
    assert trip.arrival_at - trip.departure_at == timedelta(minutes=long_route.duration_minutes)


def test_duplicate_departure_is_rejected(
    client: TestClient,
    bus_types: list[BusType],
    long_route: Route,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    del bus_types
    payload = {
        "route_id": long_route.id,
        "departure_at": _departure(),
        "base_price": "820.00",
    }

    first = client.post(ADMIN_TRIPS_URL, headers=auth_header(admin), json=payload)
    duplicate = client.post(ADMIN_TRIPS_URL, headers=auth_header(admin), json=payload)

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_unknown_route_returns_404(
    client: TestClient, admin: User, auth_header: AuthHeader
) -> None:
    response = client.post(
        ADMIN_TRIPS_URL,
        headers=auth_header(admin),
        json={"route_id": 999999, "departure_at": _departure(), "base_price": "100.00"},
    )

    assert response.status_code == 404


def test_shifting_departure_shifts_arrival(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    original_duration = trip.arrival_at - trip.departure_at
    new_departure = (trip.departure_at + timedelta(hours=3)).isoformat()

    response = client.patch(
        f"{ADMIN_TRIPS_URL}/{trip.id}",
        headers=auth_header(admin),
        json={"departure_at": new_departure},
    )

    assert response.status_code == 200
    db_session.expire_all()
    updated = db_session.get(Trip, trip.id)
    assert updated is not None
    assert updated.arrival_at - updated.departure_at == original_duration


def test_cancelling_trip_releases_seats_and_tickets(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    held = client.post(f"/api/v1/trips/{trip.id}/seats/2/hold", headers=auth_header(passenger))
    assert held.status_code == 201

    response = client.patch(
        f"{ADMIN_TRIPS_URL}/{trip.id}",
        headers=auth_header(admin),
        json={"status": TripStatus.CANCELLED.value},
    )

    assert response.status_code == 200
    db_session.expire_all()
    updated = db_session.get(Trip, trip.id)
    assert updated is not None
    assert updated.status is TripStatus.CANCELLED
    assert all(seat.status is SeatStatus.FREE for seat in updated.seats)
    assert all(ticket.status is TicketStatus.CANCELLED for ticket in updated.tickets)


def test_admin_home_reports_system_state(
    client: TestClient,
    trip: Trip,
    passenger: User,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    client.post(f"/api/v1/trips/{trip.id}/seats/1/hold", headers=auth_header(passenger))

    response = client.get("/api/v1/admin/home", headers=auth_header(admin))

    body = response.json()
    assert body["trips_total"] >= 1
    assert body["routes_total"] >= 1
    assert body["tickets_by_status"]["held"] == 1
    assert body["available_actions"]
