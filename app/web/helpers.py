"""Допоміжні речі для HTML-шару: безпечні редіректи, час, сітка салону."""

from datetime import UTC, datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.models.seat import Seat
from app.models.trip import Trip

KYIV = ZoneInfo("Europe/Kyiv")

STATUS_UA = {
    "scheduled": "у розкладі",
    "delayed": "затримка",
    "departed": "відправився",
    "cancelled": "скасовано",
    "free": "вільне",
    "held": "утримується",
    "sold": "продане",
    "paid": "оплачено",
    "passenger": "пасажир",
    "admin": "адміністратор",
}

NOTICE_UA = {
    "held": "Місце утримано на 10 хвилин. Підтвердіть оплату в кабінеті.",
    "paid": "Квиток оплачено.",
    "cancelled": "Квиток скасовано, місце знову у продажу.",
    "trip_created": "Рейс додано до розкладу, місця згенеровано з шаблону салону.",
    "trip_updated": "Розклад оновлено.",
}


def safe_next_path(value: str | None, default: str = "/") -> str:
    """Дозволяємо лише внутрішні шляхи, щоб не було open redirect."""
    if not value:
        return default
    if not value.startswith("/") or value.startswith("//") or "://" in value:
        return default
    return value


def format_kyiv(value: datetime) -> str:
    moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return moment.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")


def parse_kyiv_datetime(value: str) -> datetime:
    """Значення з <input type=datetime-local> трактуємо як київський час."""
    return datetime.fromisoformat(value).replace(tzinfo=KYIV).astimezone(UTC)


def seat_grid(trip: Trip) -> list[list[Seat | None]]:
    """Матриця салону: None — прохід, Seat — клітинка місця."""
    by_position = {(seat.row_index, seat.column_index): seat for seat in trip.seats}
    grid: list[list[Seat | None]] = []
    for row_index, row in enumerate(trip.bus_type.layout):
        grid.append(
            [
                by_position.get((row_index, column_index)) if cell else None
                for column_index, cell in enumerate(row)
            ]
        )
    return grid


def error_redirect(path: str, detail: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}error={quote(detail)}"
