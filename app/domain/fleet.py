"""Правила парку автобусів: три шаблони салону та вибір класу за довжиною маршруту.

Модуль не залежить від бази даних і сесій, тому логіку можна перевіряти
юніт-тестами без підключення до PostgreSQL.
"""

from dataclasses import dataclass

from app.models.bus import BusClass

AISLE = 0
SEAT = 1

# Верхня межа (не включно) довжини маршруту для класу автобуса.
# Усе, що довше за останній поріг, обслуговує BusClass.LARGE.
DISTANCE_THRESHOLDS_KM: tuple[tuple[int, BusClass], ...] = (
    (100, BusClass.MINI),
    (400, BusClass.STANDARD),
)


@dataclass(frozen=True)
class SeatPosition:
    """Позиція місця у схемі салону."""

    number: str
    row_index: int
    column_index: int


@dataclass(frozen=True)
class BusTypeTemplate:
    """Шаблон салону, з якого генеруються місця рейсу."""

    code: BusClass
    title: str
    layout: tuple[tuple[int, ...], ...]
    min_distance_km: int
    max_distance_km: int | None

    @property
    def row_count(self) -> int:
        return len(self.layout)

    @property
    def column_count(self) -> int:
        return max(len(row) for row in self.layout)

    @property
    def seats_count(self) -> int:
        return sum(row.count(SEAT) for row in self.layout)

    def as_matrix(self) -> list[list[int]]:
        """Схема у вигляді, придатному для збереження в JSON-колонці."""
        return [list(row) for row in self.layout]


def _rows(pattern: tuple[int, ...], count: int) -> tuple[tuple[int, ...], ...]:
    return tuple(pattern for _ in range(count))


BUS_TYPE_TEMPLATES: dict[BusClass, BusTypeTemplate] = {
    BusClass.MINI: BusTypeTemplate(
        code=BusClass.MINI,
        title="Мінібус",
        layout=_rows((1, 1, 0, 1), 4),
        min_distance_km=1,
        max_distance_km=99,
    ),
    BusClass.STANDARD: BusTypeTemplate(
        code=BusClass.STANDARD,
        title="Стандартний автобус",
        layout=_rows((1, 1, 0, 1, 1), 8),
        min_distance_km=100,
        max_distance_km=399,
    ),
    BusClass.LARGE: BusTypeTemplate(
        code=BusClass.LARGE,
        title="Туристичний автобус",
        layout=_rows((1, 1, 0, 1, 1), 12) + ((1, 1, 1, 1, 1),),
        min_distance_km=400,
        max_distance_km=None,
    ),
}


def suggest_bus_class(distance_km: int) -> BusClass:
    """Клас автобуса за довжиною маршруту: чим далі рейс, тим вищий клас."""
    if distance_km <= 0:
        raise ValueError("Довжина маршруту має бути додатною")

    for upper_bound, bus_class in DISTANCE_THRESHOLDS_KM:
        if distance_km < upper_bound:
            return bus_class
    return BusClass.LARGE


def build_seat_map(layout: list[list[int]] | tuple[tuple[int, ...], ...]) -> list[SeatPosition]:
    """Розгорнути схему салону у список місць з послідовною нумерацією."""
    positions: list[SeatPosition] = []
    counter = 0

    for row_index, row in enumerate(layout):
        for column_index, cell in enumerate(row):
            if cell != SEAT:
                continue
            counter += 1
            positions.append(
                SeatPosition(
                    number=str(counter),
                    row_index=row_index,
                    column_index=column_index,
                )
            )

    return positions
