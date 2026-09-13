"""Наповнення бази демонстраційними даними.

Запуск: python -m scripts.seed

Скрипт ідемпотентний: повторний запуск не дублює довідники, а лише додає
відсутні рейси. Клас автобуса для кожного рейсу обирається за довжиною
маршруту згідно з правилами app.domain.fleet.
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionFactory
from app.domain.fleet import BUS_TYPE_TEMPLATES, build_seat_map, suggest_bus_class
from app.models import Bus, BusType, Route, Seat, Trip

ROUTES: tuple[dict[str, object], ...] = (
    {
        "code": "KYI-ZHY",
        "origin_city": "Київ",
        "destination_city": "Житомир",
        "distance_km": 90,
        "duration_minutes": 110,
        "base_price": Decimal("220.00"),
    },
    {
        "code": "KYI-VIN",
        "origin_city": "Київ",
        "destination_city": "Вінниця",
        "distance_km": 265,
        "duration_minutes": 240,
        "base_price": Decimal("450.00"),
    },
    {
        "code": "KYI-LVV",
        "origin_city": "Київ",
        "destination_city": "Львів",
        "distance_km": 540,
        "duration_minutes": 480,
        "base_price": Decimal("790.00"),
    },
)

DEPARTURE_HOURS: tuple[int, ...] = (7, 14, 21)
DAYS_AHEAD = 3
PLATES_PER_TYPE = 2


def sync_bus_types(session: Session) -> dict[str, BusType]:
    """Створити або оновити три шаблони салону."""
    existing = {bus_type.code: bus_type for bus_type in session.scalars(select(BusType))}

    for bus_class, template in BUS_TYPE_TEMPLATES.items():
        bus_type = existing.get(bus_class)
        if bus_type is None:
            bus_type = BusType(code=bus_class)
            session.add(bus_type)
            existing[bus_class] = bus_type

        bus_type.title = template.title
        bus_type.row_count = template.row_count
        bus_type.column_count = template.column_count
        bus_type.seats_count = template.seats_count
        bus_type.layout = template.as_matrix()
        bus_type.min_distance_km = template.min_distance_km
        bus_type.max_distance_km = template.max_distance_km

    session.flush()
    return {bus_type.code.value: bus_type for bus_type in existing.values()}


def sync_buses(session: Session, bus_types: dict[str, BusType]) -> None:
    """Кілька бортів на кожен шаблон: моделей три, машин може бути будь-скільки."""
    known_plates = set(session.scalars(select(Bus.plate)))

    for bus_type in bus_types.values():
        for index in range(1, PLATES_PER_TYPE + 1):
            plate = f"AA{bus_type.id:02d}{index:02d}BX"
            if plate in known_plates:
                continue
            session.add(Bus(plate=plate, bus_type_id=bus_type.id))
            known_plates.add(plate)

    session.flush()


def sync_routes(session: Session) -> dict[str, Route]:
    existing = {route.code: route for route in session.scalars(select(Route))}

    for payload in ROUTES:
        code = str(payload["code"])
        route = existing.get(code)
        if route is None:
            route = Route(code=code)
            session.add(route)
            existing[code] = route

        route.origin_city = str(payload["origin_city"])
        route.destination_city = str(payload["destination_city"])
        route.distance_km = int(payload["distance_km"])  # type: ignore[arg-type]
        route.duration_minutes = int(payload["duration_minutes"])  # type: ignore[arg-type]

    session.flush()
    return existing


def create_trips(session: Session, routes: dict[str, Route], bus_types: dict[str, BusType]) -> int:
    """Розклад на кілька днів уперед разом зі згенерованими місцями."""
    prices = {str(payload["code"]): payload["base_price"] for payload in ROUTES}
    today = datetime.now(UTC).date()
    created = 0

    for code, route in routes.items():
        bus_class = suggest_bus_class(route.distance_km)
        bus_type = bus_types[bus_class.value]
        bus = session.scalars(
            select(Bus).where(Bus.bus_type_id == bus_type.id).order_by(Bus.id).limit(1)
        ).first()

        for day_offset in range(DAYS_AHEAD):
            for hour in DEPARTURE_HOURS:
                departure_at = datetime.combine(
                    today + timedelta(days=day_offset),
                    time(hour=hour, tzinfo=UTC),
                )

                already_exists = session.scalars(
                    select(Trip.id).where(
                        Trip.route_id == route.id,
                        Trip.departure_at == departure_at,
                    )
                ).first()
                if already_exists is not None:
                    continue

                trip = Trip(
                    route_id=route.id,
                    bus_type_id=bus_type.id,
                    bus_id=bus.id if bus is not None else None,
                    departure_at=departure_at,
                    arrival_at=departure_at + timedelta(minutes=route.duration_minutes),
                    base_price=prices[code],
                )
                session.add(trip)
                session.flush()

                session.add_all(
                    Seat(
                        trip_id=trip.id,
                        number=position.number,
                        row_index=position.row_index,
                        column_index=position.column_index,
                    )
                    for position in build_seat_map(bus_type.layout)
                )
                created += 1

    return created


def main() -> None:
    with SessionFactory() as session:
        bus_types = sync_bus_types(session)
        sync_buses(session, bus_types)
        routes = sync_routes(session)
        created_trips = create_trips(session, routes, bus_types)
        session.commit()

    print(
        f"Готово: шаблонів салону — {len(bus_types)}, "
        f"маршрутів — {len(routes)}, нових рейсів — {created_trips}."
    )


if __name__ == "__main__":
    main()
