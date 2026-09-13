"""HTML-сторінки: форми входу/реєстрації та домашні сторінки ролей.

Сторінки використовують ту саму автентифікацію, що й REST API, але токен
передається в HttpOnly-cookie, а не в заголовку. Тому анонімний доступ до
захищеної сторінки дає перенаправлення (302) замість 401.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.api.deps import PageUser, SessionDep, get_optional_user
from app.api.v1.endpoints.admin import ADMIN_ACTIONS
from app.api.v1.endpoints.tickets import PASSENGER_ACTIONS
from app.core.config import settings
from app.core.security import create_access_token
from app.models.route import Route
from app.models.trip import Trip
from app.models.user import User
from app.services import booking as booking_service
from app.services import users as users_service
from app.services.exceptions import DomainError

router = APIRouter(tags=["pages"], include_in_schema=False)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

LOGIN_URL = "/login"
PASSENGER_HOME_URL = "/home"
ADMIN_HOME_URL = "/admin"


def home_url_for(user: User) -> str:
    """Кожна роль має власну домашню сторінку."""
    return ADMIN_HOME_URL if user.is_admin else PASSENGER_HOME_URL


def _set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.access_token_cookie,
        value=create_access_token(user_id=user.id, role=user.role.value),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
    )


@router.get(LOGIN_URL, response_class=HTMLResponse, summary="Форма входу")
def login_form(request: Request, session: SessionDep) -> Response:
    user = get_optional_user(session, None, request.cookies.get(settings.access_token_cookie))
    if user is not None:
        return RedirectResponse(home_url_for(user), status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"current_user": None, "registered": "registered" in request.query_params},
    )


@router.post(LOGIN_URL, summary="Обробка форми входу")
def login_submit(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    try:
        user = users_service.authenticate(session, email, password)
    except DomainError as exc:
        # Форму показуємо повторно з повідомленням, а не віддаємо JSON-помилку.
        return templates.TemplateResponse(
            request,
            "login.html",
            {"current_user": None, "error": exc.detail, "email": email},
            status_code=exc.status_code,
        )

    response = RedirectResponse(home_url_for(user), status_code=status.HTTP_302_FOUND)
    _set_auth_cookie(response, user)
    return response


@router.get("/register", response_class=HTMLResponse, summary="Форма реєстрації")
def register_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "register.html", {"current_user": None})


@router.post("/register", summary="Обробка форми реєстрації")
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
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "current_user": None,
                "error": exc.detail,
                "email": email,
                "full_name": full_name,
            },
            status_code=exc.status_code,
        )

    return RedirectResponse(f"{LOGIN_URL}?registered=1", status_code=status.HTTP_302_FOUND)


@router.get("/logout", summary="Вихід")
def logout() -> Response:
    response = RedirectResponse(LOGIN_URL, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(settings.access_token_cookie)
    return response


@router.get(PASSENGER_HOME_URL, response_class=HTMLResponse, summary="Кабінет пасажира")
def passenger_home_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    if user.is_admin:
        return RedirectResponse(ADMIN_HOME_URL, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request,
        "passenger_home.html",
        {
            "current_user": user,
            "tickets": booking_service.list_user_tickets(session, user),
            "actions": PASSENGER_ACTIONS,
        },
    )


@router.get(ADMIN_HOME_URL, response_class=HTMLResponse, summary="Панель перевізника")
def admin_home_page(request: Request, user: PageUser, session: SessionDep) -> Response:
    if not user.is_admin:
        # Вертикальне розмежування на рівні сторінок: 403, а не перенаправлення.
        return templates.TemplateResponse(
            request,
            "forbidden.html",
            {"current_user": user, "detail": "Розділ доступний лише адміністраторам"},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    stats = {
        "users_total": session.scalar(select(func.count(User.id))) or 0,
        "routes_total": session.scalar(select(func.count(Route.id))) or 0,
        "trips_total": session.scalar(select(func.count(Trip.id))) or 0,
        "tickets_by_status": booking_service.count_tickets_by_status(session),
    }

    return templates.TemplateResponse(
        request,
        "admin_home.html",
        {"current_user": user, "stats": stats, "actions": ADMIN_ACTIONS},
    )
