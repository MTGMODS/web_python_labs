"""Реєстрація та автентифікація."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, UserRole
from tests.conftest import PASSWORD

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"


def _register_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "new.passenger@busline.ua",
        "password": "strong-password-1",
        "full_name": "Новий Пасажир",
    }
    payload.update(overrides)
    return payload


def test_registration_creates_passenger(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_register_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == UserRole.PASSENGER.value
    assert body["is_active"] is True


def test_registration_never_returns_password(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_register_payload())

    body = response.json()
    assert "password" not in body
    assert "password_hash" not in body


def test_password_is_stored_only_as_hash(client: TestClient, db_session: Session) -> None:
    client.post(REGISTER_URL, json=_register_payload(password="plain-text-secret"))

    user = db_session.query(User).filter_by(email="new.passenger@busline.ua").one()
    assert user.password_hash != "plain-text-secret"
    assert user.password_hash.startswith("$2")


def test_registration_rejects_duplicate_email(client: TestClient) -> None:
    client.post(REGISTER_URL, json=_register_payload())
    response = client.post(REGISTER_URL, json=_register_payload(full_name="Інше Імʼя"))

    assert response.status_code == 409


def test_registration_normalizes_email_case(client: TestClient) -> None:
    client.post(REGISTER_URL, json=_register_payload(email="Mixed.Case@Busline.UA"))
    duplicate = client.post(REGISTER_URL, json=_register_payload(email="mixed.case@busline.ua"))

    assert duplicate.status_code == 409


def test_registration_validates_input(client: TestClient) -> None:
    assert (
        client.post(REGISTER_URL, json=_register_payload(email="not-an-email")).status_code == 422
    )
    assert client.post(REGISTER_URL, json=_register_payload(password="short")).status_code == 422
    assert client.post(REGISTER_URL, json=_register_payload(full_name="X")).status_code == 422


def test_registration_cannot_grant_admin_role(client: TestClient) -> None:
    """Роль не є частиною контракту реєстрації, тому підвищити права неможливо."""
    response = client.post(REGISTER_URL, json=_register_payload(role="admin"))

    assert response.status_code == 201
    assert response.json()["role"] == UserRole.PASSENGER.value


def test_login_returns_token_and_sets_cookie(client: TestClient, passenger: User) -> None:
    response = client.post(
        LOGIN_URL,
        data={"username": passenger.email, "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert settings.access_token_cookie in response.cookies


def test_login_rejects_wrong_password(client: TestClient, passenger: User) -> None:
    response = client.post(
        LOGIN_URL,
        data={"username": passenger.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        LOGIN_URL,
        data={"username": "nobody@busline.ua", "password": PASSWORD},
    )

    assert response.status_code == 401


def test_login_error_does_not_reveal_whether_account_exists(
    client: TestClient, passenger: User
) -> None:
    wrong_password = client.post(
        LOGIN_URL, data={"username": passenger.email, "password": "wrong-password"}
    )
    unknown_email = client.post(
        LOGIN_URL, data={"username": "nobody@busline.ua", "password": PASSWORD}
    )

    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_login_rejects_deactivated_account(
    client: TestClient, db_session: Session, passenger: User
) -> None:
    passenger.is_active = False
    db_session.commit()

    response = client.post(LOGIN_URL, data={"username": passenger.email, "password": PASSWORD})

    assert response.status_code == 401


def test_profile_requires_valid_token(
    client: TestClient, passenger: User, auth_header: object
) -> None:
    valid = client.get(ME_URL, headers=auth_header(passenger))  # type: ignore[operator]
    forged = client.get(ME_URL, headers={"Authorization": "Bearer not.a.real.token"})

    assert valid.status_code == 200
    assert valid.json()["email"] == passenger.email
    assert forged.status_code == 401


def test_logout_clears_cookie(client: TestClient, passenger: User) -> None:
    client.post(LOGIN_URL, data={"username": passenger.email, "password": PASSWORD})
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert client.cookies.get(settings.access_token_cookie) in (None, "")
