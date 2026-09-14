"""Перевірка каркаса застосунку."""

from fastapi.testclient import TestClient


def test_root_is_the_public_timetable(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Квитки на міжміські автобуси" in response.text
    assert "Bus Tickets Platform" not in response.text
    assert '"docs":"/docs"' not in response.text
    assert 'href="/docs"' not in response.text
    assert 'href="/redoc"' not in response.text
    assert 'href="/health"' not in response.text
    assert 'href="/api/v1"' not in response.text


def test_swagger_is_available_but_not_linked_from_the_site(client: TestClient) -> None:
    """Swagger лишається за прямим URL для розробки, сайт на нього не посилається."""
    docs = client.get("/docs")
    redoc = client.get("/redoc")

    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
    assert redoc.status_code == 200
    assert 'href="/docs"' not in client.get("/").text
    assert 'href="/docs"' not in client.get("/login").text


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
