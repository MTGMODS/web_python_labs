"""Перевірка каркаса застосунку."""

from fastapi.testclient import TestClient


def test_root_returns_service_info(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["api"] == "/api/v1"


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
