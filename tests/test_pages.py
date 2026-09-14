"""Домашні сторінки-заглушки та вхід через веб-форму."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import User
from tests.conftest import PASSWORD

AuthHeader = Callable[[User], dict[str, str]]


def _login_via_form(client: TestClient, user: User) -> None:
    response = client.post(
        "/login",
        data={"email": user.email, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_form_login_redirects_passenger_to_own_home(client: TestClient, passenger: User) -> None:
    response = client.post(
        "/login",
        data={"email": passenger.email, "password": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/home"
    assert settings.access_token_cookie in response.cookies


def test_form_login_redirects_admin_to_admin_home(client: TestClient, admin: User) -> None:
    response = client.post(
        "/login",
        data={"email": admin.email, "password": PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin"


def test_form_login_shows_error_instead_of_json(client: TestClient, passenger: User) -> None:
    response = client.post(
        "/login",
        data={"email": passenger.email, "password": "wrong-password"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "text/html" in response.headers["content-type"]
    assert "Невірний email або пароль" in response.text


def test_passenger_home_page_renders(client: TestClient, passenger: User) -> None:
    _login_via_form(client, passenger)

    response = client.get("/home")

    assert response.status_code == 200
    assert passenger.full_name in response.text
    assert "Кабінет пасажира" in response.text


def test_admin_home_page_renders(client: TestClient, admin: User) -> None:
    _login_via_form(client, admin)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Панель перевізника" in response.text


def test_passenger_on_admin_page_gets_403(client: TestClient, passenger: User) -> None:
    """Вертикальне розмежування на рівні сторінок."""
    _login_via_form(client, passenger)

    response = client.get("/admin")

    assert response.status_code == 403
    assert "доступ заборонено" in response.text.lower()


def test_admin_visiting_passenger_home_is_redirected(client: TestClient, admin: User) -> None:
    _login_via_form(client, admin)

    response = client.get("/home", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin"


def test_registration_via_form_creates_account(client: TestClient) -> None:
    response = client.post(
        "/register",
        data={
            "full_name": "Веб Пасажир",
            "email": "web.passenger@busline.ua",
            "password": "strong-password-1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")

    logged_in = client.post(
        "/login",
        data={"email": "web.passenger@busline.ua", "password": "strong-password-1"},
        follow_redirects=False,
    )
    assert logged_in.status_code == 302


def test_duplicate_registration_via_form_shows_error(client: TestClient, passenger: User) -> None:
    response = client.post(
        "/register",
        data={
            "full_name": "Дублікат",
            "email": passenger.email,
            "password": "strong-password-1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert "вже існує" in response.text


def test_logout_redirects_to_login(client: TestClient, passenger: User) -> None:
    _login_via_form(client, passenger)

    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"
