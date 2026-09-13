"""Фікстури тестів.

Інтеграційні тести працюють на окремій базі PostgreSQL (TEST_DATABASE_URL), а не
на SQLite: перевіряються блокування рядків і часткові унікальні індекси, яких на
іншому рушії просто не існує.

Кожен тест виконується у власній транзакції, яка відкочується після завершення.
Режим join_transaction_mode="create_savepoint" дозволяє сервісному шару викликати
session.commit() усередині тесту, не руйнуючи зовнішню транзакцію.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.domain.fleet import BUS_TYPE_TEMPLATES
from app.main import app
from app.models import BusType, Route, Trip, User, UserRole
from app.services import schedule as schedule_service
from app.services import users as users_service

PASSWORD = "passenger123"


def _ensure_test_database() -> None:
    """Створити тестову базу, якщо її ще немає."""
    url = make_url(settings.test_database_url)
    maintenance_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")

    with maintenance_engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))

    maintenance_engine.dispose()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _ensure_test_database()
    test_engine = create_engine(settings.test_database_url)

    # Повне перестворення схеми: прибирає і таблиці, і типи ENUM з попередніх прогонів.
    with test_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_header() -> Callable[[User], dict[str, str]]:
    """Заголовок Authorization для вказаного користувача."""

    def _make(user: User) -> dict[str, str]:
        token = create_access_token(user_id=user.id, role=user.role.value)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def passenger(db_session: Session) -> User:
    return users_service.create_user(
        db_session,
        email="passenger.one@busline.ua",
        password=PASSWORD,
        full_name="Перший Пасажир",
    )


@pytest.fixture
def other_passenger(db_session: Session) -> User:
    return users_service.create_user(
        db_session,
        email="passenger.two@busline.ua",
        password=PASSWORD,
        full_name="Другий Пасажир",
    )


@pytest.fixture
def admin(db_session: Session) -> User:
    return users_service.create_user(
        db_session,
        email="dispatcher@busline.ua",
        password=PASSWORD,
        full_name="Адміністратор Перевізника",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def bus_types(db_session: Session) -> list[BusType]:
    """Три шаблони салону з доменних правил."""
    created = []
    for template in BUS_TYPE_TEMPLATES.values():
        bus_type = BusType(
            code=template.code,
            title=template.title,
            row_count=template.row_count,
            column_count=template.column_count,
            seats_count=template.seats_count,
            layout=template.as_matrix(),
            min_distance_km=template.min_distance_km,
            max_distance_km=template.max_distance_km,
        )
        db_session.add(bus_type)
        created.append(bus_type)

    db_session.flush()
    return created


@pytest.fixture
def long_route(db_session: Session) -> Route:
    """Маршрут понад 400 км — за правилом отримує автобус класу large."""
    route = Route(
        code="KYI-LVV",
        origin_city="Київ",
        destination_city="Львів",
        distance_km=540,
        duration_minutes=480,
    )
    db_session.add(route)
    db_session.flush()
    return route


@pytest.fixture
def trip(db_session: Session, bus_types: list[BusType], long_route: Route) -> Trip:
    del bus_types
    return schedule_service.create_trip(
        db_session,
        route_id=long_route.id,
        departure_at=datetime.now(UTC) + timedelta(days=2),
        base_price=Decimal("790.00"),
    )
