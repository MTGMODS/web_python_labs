"""Веб-інтерфейс MVP: розклад, схема місць, оплата, адмін-розклад."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Seat, SeatStatus, Trip, User
from app.models.bus import BusType
from app.models.route import Route
from app.services import schedule as schedule_service
from app.web.helpers import format_kyiv
from tests.conftest import PASSWORD


def _login(client: TestClient, user: User) -> None:
    response = client.post(
        "/login",
        data={"email": user.email, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_catalog_empty_filters_stay_html(client: TestClient, trip: Trip) -> None:
    """Порожні поля форми «Показати рейси» не повинні давати JSON 422."""
    blank = client.get("/?route_id=&departure_date=")
    route_only = client.get(f"/?route_id={trip.route_id}&departure_date=")

    assert blank.status_code == 200
    assert "text/html" in blank.headers["content-type"]
    assert "Обрати місця" in blank.text
    assert route_only.status_code == 200
    assert "text/html" in route_only.headers["content-type"]
    assert trip.route.origin_city in route_only.text
    assert "date_from_datetime_parsing" not in route_only.text


def test_catalog_invalid_date_does_not_return_json(client: TestClient) -> None:
    response = client.get("/?departure_date=not-a-date", follow_redirects=False)

    assert response.status_code == 303
    assert "application/json" not in response.headers.get("content-type", "")
    assert "error=" in response.headers["location"]


def test_catalog_lists_seeded_style_trip(client: TestClient, trip: Trip) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Київ" in response.text
    assert "Львів" in response.text
    assert "Обрати місця" in response.text
    assert format_kyiv(trip.departure_at) in response.text
    assert f"/trips/{trip.id}" in response.text


def test_seat_map_page_shows_free_seats(client: TestClient, trip: Trip) -> None:
    response = client.get(f"/trips/{trip.id}")

    assert response.status_code == 200
    assert "Схема салону" in response.text
    assert "login?next=/trips/" in response.text


def test_unknown_trip_page_is_404(client: TestClient) -> None:
    response = client.get("/trips/999999")

    assert response.status_code == 404


def test_passenger_can_hold_pay_and_cancel_via_site(
    client: TestClient,
    db_session: Session,
    trip: Trip,
    passenger: User,
) -> None:
    _login(client, passenger)

    hold = client.post(
        f"/trips/{trip.id}/seats/3/hold",
        follow_redirects=False,
    )
    assert hold.status_code == 303
    assert hold.headers["location"] == "/home?notice=held"

    home = client.get("/home")
    assert home.status_code == 200
    assert "утримується" in home.text
    assert "/tickets/" in home.text
    assert format_kyiv(trip.departure_at) in home.text

    ticket_id = _ticket_id_from_home(home.text)
    pay = client.post(f"/tickets/{ticket_id}/pay", follow_redirects=False)
    assert pay.status_code == 303

    db_session.expire_all()
    seat = db_session.query(Seat).filter_by(trip_id=trip.id, number="3").one()
    assert seat.status is SeatStatus.SOLD

    cancel = client.post(f"/tickets/{ticket_id}/cancel", follow_redirects=False)
    assert cancel.status_code == 303
    db_session.expire_all()
    assert (
        db_session.query(Seat).filter_by(trip_id=trip.id, number="3").one().status
        is SeatStatus.FREE
    )


def test_anonymous_hold_redirects_to_login(client: TestClient, trip: Trip) -> None:
    response = client.post(f"/trips/{trip.id}/seats/4/hold", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")


def test_login_returns_to_trip_after_hold_redirect(
    client: TestClient, trip: Trip, passenger: User
) -> None:
    response = client.post(
        "/login",
        data={
            "email": passenger.email,
            "password": PASSWORD,
            "next": f"/trips/{trip.id}",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == f"/trips/{trip.id}"


def test_admin_trips_page_renders(client: TestClient, admin: User, trip: Trip) -> None:
    _login(client, admin)

    page = client.get("/admin/trips")

    assert page.status_code == 200
    assert "Додати рейс" in page.text
    assert trip.route.origin_city in page.text


def test_admin_can_add_trip_and_change_status(
    client: TestClient,
    db_session: Session,
    admin: User,
    long_route: Route,
    bus_types: list[BusType],
) -> None:
    del bus_types
    _login(client, admin)

    created = client.post(
        "/admin/trips",
        data={
            "route_id": str(long_route.id),
            "departure_at": (datetime.now(UTC) + timedelta(days=9)).strftime("%Y-%m-%dT08:00"),
            "base_price": "640.00",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    trip = schedule_service.list_trips(db_session, route_id=long_route.id)[-1]
    assert trip.base_price == Decimal("640.00")

    updated = client.post(
        f"/admin/trips/{trip.id}/status",
        data={"status": "cancelled"},
        follow_redirects=False,
    )
    assert updated.status_code == 303
    db_session.refresh(trip)
    assert trip.status.value == "cancelled"


def test_passenger_cannot_open_admin_trips(client: TestClient, passenger: User) -> None:
    _login(client, passenger)

    response = client.get("/admin/trips")

    assert response.status_code == 403
    assert "доступ заборонено" in response.text.lower()


def test_admin_tickets_page_lists_passenger_ticket(
    client: TestClient,
    trip: Trip,
    passenger: User,
    admin: User,
) -> None:
    _login(client, passenger)
    client.post(f"/trips/{trip.id}/seats/15/hold", follow_redirects=False)
    client.get("/logout", follow_redirects=False)

    _login(client, admin)
    response = client.get("/admin/tickets")

    assert response.status_code == 200
    assert passenger.full_name in response.text
    assert "утримується" in response.text


def _ticket_id_from_home(html: str) -> int:
    marker = "/tickets/"
    start = html.index(marker) + len(marker)
    digits = []
    for char in html[start:]:
        if char.isdigit():
            digits.append(char)
        else:
            break
    return int("".join(digits))
