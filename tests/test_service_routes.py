"""Перевірка каркаса застосунку."""

from fastapi.testclient import TestClient


def test_root_is_the_public_timetable(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Обрати місця" in response.text
    assert 'href="/docs"' not in response.text


def test_swagger_ui_is_disabled(client: TestClient) -> None:
    """Сайт — основний інтерфейс, Swagger викладачу більше не потрібен."""
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_liveness_does_not_touch_database(client: TestClient) -> None:
    """Liveness має відповідати навіть за недоступної бази."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_contains_domain_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/bus-types" in paths
    assert "/api/v1/trips" in paths
    assert "/api/v1/trips/{trip_id}/seats" in paths
