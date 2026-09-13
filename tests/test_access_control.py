"""Розмежування прав доступу.

Покриті всі чотири сценарії з умови роботи: анонімний доступ, автентифікація,
вертикальне розмежування ролей і горизонтальне розмежування прав (IDOR).
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models import Trip, User

AuthHeader = Callable[[User], dict[str, str]]

PROTECTED_API_ROUTES = [
    ("GET", "/api/v1/me/home"),
    ("GET", "/api/v1/tickets/my"),
    ("GET", "/api/v1/admin/home"),
    ("GET", "/api/v1/admin/tickets"),
]

ADMIN_ONLY_ROUTES = [
    ("GET", "/api/v1/admin/home"),
    ("GET", "/api/v1/admin/tickets"),
]


@pytest.mark.parametrize(("method", "url"), PROTECTED_API_ROUTES)
def test_anonymous_access_to_api_returns_401(client: TestClient, method: str, url: str) -> None:
    response = client.request(method, url)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_anonymous_access_to_page_redirects_to_login(client: TestClient) -> None:
    response = client.get("/home", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_login_page_is_public(client: TestClient) -> None:
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_authenticated_passenger_reaches_own_home(
    client: TestClient, passenger: User, auth_header: AuthHeader
) -> None:
    response = client.get("/api/v1/me/home", headers=auth_header(passenger))

    assert response.status_code == 200
    assert response.json()["role"] == "passenger"


@pytest.mark.parametrize(("method", "url"), ADMIN_ONLY_ROUTES)
def test_passenger_is_denied_admin_routes(
    client: TestClient,
    passenger: User,
    auth_header: AuthHeader,
    method: str,
    url: str,
) -> None:
    """Вертикальне розмежування: звичайний користувач не має доступу до адмінки."""
    response = client.request(method, url, headers=auth_header(passenger))

    assert response.status_code == 403


def test_admin_reaches_admin_home(client: TestClient, admin: User, auth_header: AuthHeader) -> None:
    response = client.get("/api/v1/admin/home", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_passenger_cannot_create_trip(
    client: TestClient, passenger: User, auth_header: AuthHeader, long_route: Trip
) -> None:
    response = client.post(
        "/api/v1/admin/trips",
        headers=auth_header(passenger),
        json={
            "route_id": long_route.id,
            "departure_at": "2027-05-01T08:00:00Z",
            "base_price": "500.00",
        },
    )

    assert response.status_code == 403


def test_passenger_cannot_modify_another_profile(
    client: TestClient,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    """Горизонтальне розмежування (IDOR) для профілю користувача."""
    response = client.patch(
        f"/api/v1/users/{other_passenger.id}",
        headers=auth_header(passenger),
        json={"full_name": "Перезаписане Імʼя"},
    )

    assert response.status_code == 403


def test_passenger_can_modify_own_profile(
    client: TestClient, passenger: User, auth_header: AuthHeader
) -> None:
    response = client.patch(
        f"/api/v1/users/{passenger.id}",
        headers=auth_header(passenger),
        json={"full_name": "Оновлене Імʼя"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Оновлене Імʼя"


def test_admin_can_modify_any_profile(
    client: TestClient, admin: User, passenger: User, auth_header: AuthHeader
) -> None:
    response = client.patch(
        f"/api/v1/users/{passenger.id}",
        headers=auth_header(admin),
        json={"full_name": "Виправлено Адміністратором"},
    )

    assert response.status_code == 200


def test_passenger_cannot_touch_another_ticket(
    client: TestClient,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    """Горизонтальне розмежування (IDOR) для сутності предметної області."""
    created = client.post(
        f"/api/v1/trips/{trip.id}/seats/7/hold",
        headers=auth_header(passenger),
    )
    ticket_id = created.json()["id"]

    intruder = auth_header(other_passenger)
    pay_attempt = client.post(f"/api/v1/tickets/{ticket_id}/pay", headers=intruder)
    cancel_attempt = client.post(f"/api/v1/tickets/{ticket_id}/cancel", headers=intruder)

    assert pay_attempt.status_code == 403
    assert cancel_attempt.status_code == 403


def test_ticket_list_is_scoped_to_owner(
    client: TestClient,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    auth_header: AuthHeader,
) -> None:
    client.post(f"/api/v1/trips/{trip.id}/seats/1/hold", headers=auth_header(passenger))
    client.post(f"/api/v1/trips/{trip.id}/seats/2/hold", headers=auth_header(other_passenger))

    response = client.get("/api/v1/tickets/my", headers=auth_header(passenger))

    tickets = response.json()
    assert len(tickets) == 1
    assert {ticket["user_id"] for ticket in tickets} == {passenger.id}


def test_admin_sees_all_tickets(
    client: TestClient,
    trip: Trip,
    passenger: User,
    other_passenger: User,
    admin: User,
    auth_header: AuthHeader,
) -> None:
    client.post(f"/api/v1/trips/{trip.id}/seats/1/hold", headers=auth_header(passenger))
    client.post(f"/api/v1/trips/{trip.id}/seats/2/hold", headers=auth_header(other_passenger))

    response = client.get("/api/v1/admin/tickets", headers=auth_header(admin))

    assert response.status_code == 200
    assert len(response.json()) == 2
