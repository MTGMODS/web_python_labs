"""HTML-сайт: розклад, схема місць, кабінети пасажира й перевізника.

Усі бізнес-операції йдуть у ті самі сервіси, що й REST API. Різниця лише в
транспорті: форми й cookie замість JSON і заголовка Authorization.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select

from app.api.deps import OptionalUser, PageUser, SessionDep, get_optional_user
from app.core.config import settings
from app.core.security import create_access_token
from app.models.route import Route
from app.models.trip import Trip, TripStatus
from app.models.user import User
from app.services import booking as booking_service
from app.services import schedule as schedule_service
from app.services import users as users_service
from app.services.exceptions import DomainError, NotFoundError
from app.web.helpers import (
    NOTICE_UA,
    STATUS_UA,
    error_redirect,
    format_kyiv,
    parse_kyiv_datetime,
    safe_next_path,
    seat_grid,
)

router = APIRouter(tags=["pages"], include_in_schema=False)

_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)
_jinja_env.filters["kyiv"] = format_kyiv
_jinja_env.globals["kyiv"] = format_kyiv
templates = Jinja2Templates(env=_jinja_env)

LOGIN_URL = "/login"
PASSENGER_HOME_URL = "/home"
ADMIN_HOME_URL = "/admin"
TRIP_STATUS_CHOICES = [(item.value, STATUS_UA[item.value]) for item in TripStatus]


def home_url_for(user: User) -> str:
    return ADMIN_HOME_URL if user.is_admin else PASSENGER_HOME_URL


def _set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.access_token_cookie,
        value=create_access_token(user_id=user.id, role=user.role.value),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
    )


def _page(
    request: Request,
    name: str,
    current_user: User | None,
    status_code: int = 200,
    **context: Any,
) -> Response:
    payload = {
        "current_user": current_user,
        "status_ua": STATUS_UA,
        "kyiv": format_kyiv,
        "notice": NOTICE_UA.get(request.query_params.get("notice", ""), ""),
        "error": request.query_params.get("error", ""),
        **context,
    }
    if request.query_params.get("notice") and not payload["notice"]:
        payload["notice"] = request.query_params.get("notice")
    return templates.TemplateResponse(request, name, payload, status_code=status_code)


def _forbidden(request: Request, user: User) -> Response:
    return _page(
        request,
        "forbidden.html",
        user,
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Розділ доступний лише адміністраторам",
    )


def _require_admin(request: Request, user: User) -> Response | None:
    if user.is_admin:
        return None
    return _forbidden(request, user)


@router.get(LOGIN_URL, response_class=HTMLResponse)
def login_form(
    request: Request,
    session: SessionDep,
    next: str | None = None,
) -> Response:
    user = get_optional_user(session, None, request.cookies.get(settings.access_token_cookie))
    if user is not None:
        return RedirectResponse(
            safe_next_path(next, home_url_for(user)),
            status_code=status.HTTP_302_FOUND,
        )
    return _page(
        request,
        "login.html",
        None,
        registered="registered" in request.query_params,
        next_path=safe_next_path(next, "/"),
        email=None,
    )


@router.post(LOGIN_URL)
def login_submit(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        user = users_service.authenticate(session, email, password)
    except DomainError as exc:
        return _page(
            request,
            "login.html",
            None,
            status_code=exc.status_code,
            error=exc.detail,
            email=email,
            next_path=safe_next_path(next, "/"),
        )

    target = safe_next_path(next, home_url_for(user))
    if not user.is_admin and target.startswith("/admin"):
        target = PASSENGER_HOME_URL
    response = RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    _set_auth_cookie(response, user)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request) -> Response:
    return _page(request, "register.html", None)


@router.post("/register")
def register_submit(
    request: Request,
    session: SessionDep,
    full_name: Annotated[str, Form(min_length=2, max_length=128)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form(min_length=8, max_length=72)],
) -> Response:
    try:
        users_service.create_user(
            session,
            email=email,
            password=password,
            full_name=full_name,
        )
    except DomainError as exc:
        return _page(
            request,
            "register.html",
            None,
            status_code=exc.status_code,
            error=exc.detail,
            email=email,
            full_name=full_name,
        )
    return RedirectResponse(f"{LOGIN_URL}?registered=1", status_code=status.HTTP_302_FOUND)


@router.get("/logout")
def logout() -> Response:
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(settings.access_token_cookie)
    return response


@router.get("/", response_class=HTMLResponse)
def trips_page(
    request: Request,
    session: SessionDep,
    user: OptionalUser,
    route_id: int | None = None,
    departure_date: date | None = None,
) -> Response:
    trips = schedule_service.list_trips(
        session,
        route_id=route_id,
        departure_date=departure_date,
    )
    return _page(
        request,
        "trips.html",
        user,
        routes=schedule_service.list_routes(session),
        trips=trips,
        free_counts=schedule_service.free_seat_counts(session, [trip.id for trip in trips]),
        selected_route_id=route_id,
        selected_date=departure_date.isoformat() if departure_date else "",
    )


@router.get("/trips/{trip_id}", response_class=HTMLResponse)
def trip_seats_page(
    request: Request,
    trip_id: int,
    session: SessionDep,
    user: OptionalUser,
) -> Response:
    try:
        trip = schedule_service.get_trip(session, trip_id)
    except NotFoundError as exc:
        return _page(request, "not_found.html", user, status_code=404, detail=exc.detail)
    return _page(request, "trip_seats.html", user, trip=trip, grid=seat_grid(trip))


@router.post("/trips/{trip_id}/seats/{seat_number}/hold")
def hold_seat_form(
    trip_id: int,
    seat_number: str,
    user: PageUser,
    session: SessionDep,
) -> Response:
    try:
        booking_service.hold_seat(session, user, trip_id, seat_number)
    except DomainError as exc:
        return RedirectResponse(error_redirect(f"/trips/{trip_id}", exc.detail), status_code=303)
    return RedirectResponse("/home?notice=held", status_code=303)


@router.get(PASSENGER_HOME_URL, response_class=HTMLResponse)
def passenger_home_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    if user.is_admin:
        return RedirectResponse(ADMIN_HOME_URL, status_code=status.HTTP_302_FOUND)
    return _page(
        request,
        "passenger_home.html",
        user,
        tickets=booking_service.list_user_tickets(session, user),
    )


@router.post("/tickets/{ticket_id}/pay")
def pay_ticket_form(ticket_id: int, user: PageUser, session: SessionDep) -> Response:
    try:
        booking_service.pay_ticket(session, user, ticket_id)
    except DomainError as exc:
        return RedirectResponse(error_redirect("/home", exc.detail), status_code=303)
    return RedirectResponse("/home?notice=paid", status_code=303)


@router.post("/tickets/{ticket_id}/cancel")
def cancel_ticket_form(
    ticket_id: int,
    user: PageUser,
    session: SessionDep,
    next: Annotated[str | None, Form()] = None,
) -> Response:
    fallback = "/admin/tickets" if user.is_admin else "/home"
    target = safe_next_path(next, fallback)
    try:
        booking_service.cancel_ticket(session, user, ticket_id)
    except DomainError as exc:
        return RedirectResponse(error_redirect(target, exc.detail), status_code=303)
    notice = "&" if "?" in target else "?"
    return RedirectResponse(f"{target}{notice}notice=cancelled", status_code=303)


@router.get(ADMIN_HOME_URL, response_class=HTMLResponse)
def admin_home_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    denied = _require_admin(request, user)
    if denied is not None:
        return denied
    stats = {
        "users_total": session.scalar(select(func.count(User.id))) or 0,
        "routes_total": session.scalar(select(func.count(Route.id))) or 0,
        "trips_total": session.scalar(select(func.count(Trip.id))) or 0,
        "tickets_by_status": booking_service.count_tickets_by_status(session),
    }
    return _page(request, "admin_home.html", user, stats=stats)


@router.get("/admin/trips", response_class=HTMLResponse)
def admin_trips_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    denied = _require_admin(request, user)
    if denied is not None:
        return denied
    return _page(
        request,
        "admin_trips.html",
        user,
        routes=schedule_service.list_routes(session),
        trips=schedule_service.list_trips(session, limit=200),
        trip_statuses=TRIP_STATUS_CHOICES,
    )


@router.post("/admin/trips")
def admin_create_trip(
    request: Request,
    user: PageUser,
    session: SessionDep,
    route_id: Annotated[int, Form()],
    departure_at: Annotated[str, Form()],
    base_price: Annotated[str, Form()],
) -> Response:
    denied = _require_admin(request, user)
    if denied is not None:
        return denied
    try:
        price = Decimal(base_price)
        schedule_service.create_trip(
            session,
            route_id=route_id,
            departure_at=parse_kyiv_datetime(departure_at),
            base_price=price,
        )
    except (DomainError, InvalidOperation, ValueError) as exc:
        detail = exc.detail if isinstance(exc, DomainError) else "Перевірте час і ціну рейсу"
        return RedirectResponse(error_redirect("/admin/trips", detail), status_code=303)
    return RedirectResponse("/admin/trips?notice=trip_created", status_code=303)


@router.post("/admin/trips/{trip_id}/status")
def admin_update_trip_status(
    request: Request,
    trip_id: int,
    user: PageUser,
    session: SessionDep,
    status_value: Annotated[str, Form(alias="status")],
) -> Response:
    denied = _require_admin(request, user)
    if denied is not None:
        return denied
    try:
        schedule_service.update_trip(session, trip_id, status=TripStatus(status_value))
    except (DomainError, ValueError) as exc:
        detail = exc.detail if isinstance(exc, DomainError) else "Невідомий статус рейсу"
        return RedirectResponse(error_redirect("/admin/trips", detail), status_code=303)
    return RedirectResponse("/admin/trips?notice=trip_updated", status_code=303)


@router.get("/admin/tickets", response_class=HTMLResponse)
def admin_tickets_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    denied = _require_admin(request, user)
    if denied is not None:
        return denied
    return _page(
        request,
        "admin_tickets.html",
        user,
        tickets=booking_service.list_all_tickets(session, limit=200),
    )
