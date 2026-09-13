"""Тести доменних правил парку автобусів."""

import pytest

from app.domain.fleet import BUS_TYPE_TEMPLATES, build_seat_map, suggest_bus_class
from app.models.bus import BusClass


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [
        (15, BusClass.MINI),
        (99, BusClass.MINI),
        (100, BusClass.STANDARD),
        (399, BusClass.STANDARD),
        (400, BusClass.LARGE),
        (1200, BusClass.LARGE),
    ],
)
def test_bus_class_depends_on_distance(distance_km: int, expected: BusClass) -> None:
    assert suggest_bus_class(distance_km) is expected


def test_bus_class_rejects_non_positive_distance() -> None:
    with pytest.raises(ValueError):
        suggest_bus_class(0)


def test_templates_cover_all_classes_without_distance_gaps() -> None:
    assert set(BUS_TYPE_TEMPLATES) == set(BusClass)

    ordered = sorted(BUS_TYPE_TEMPLATES.values(), key=lambda template: template.min_distance_km)
    for current, following in zip(ordered, ordered[1:], strict=False):
        assert current.max_distance_km is not None
        assert current.max_distance_km + 1 == following.min_distance_km

    assert ordered[-1].max_distance_km is None


@pytest.mark.parametrize("bus_class", list(BusClass))
def test_seat_map_matches_template_capacity(bus_class: BusClass) -> None:
    template = BUS_TYPE_TEMPLATES[bus_class]
    seats = build_seat_map(template.layout)

    assert len(seats) == template.seats_count
    assert [seat.number for seat in seats] == [str(i) for i in range(1, len(seats) + 1)]
    assert len({(seat.row_index, seat.column_index) for seat in seats}) == len(seats)


def test_seat_map_skips_aisle_cells() -> None:
    seats = build_seat_map([[1, 1, 0, 1]])

    assert [seat.column_index for seat in seats] == [0, 1, 3]
