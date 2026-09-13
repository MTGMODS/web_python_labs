"""Спільні фікстури тестів."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Клієнт для маршрутів, які не потребують підключення до бази."""
    return TestClient(app)
