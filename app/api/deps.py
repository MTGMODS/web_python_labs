"""Спільні залежності API: сесія бази та перевірка доступу.

Ядро автентифікації одне. Відрізняється лише реакція на її відсутність:
REST-маршрути повертають 401, а HTML-сторінки перенаправляють на форму входу.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_session
from app.models.user import User

SessionDep = Annotated[Session, Depends(get_session)]

# auto_error=False: рішення про код відповіді ухвалюємо самі, бо для сторінок
# потрібне перенаправлення, а не 401.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

TokenFromHeader = Annotated[str | None, Depends(oauth2_scheme)]
TokenFromCookie = Annotated[str | None, Cookie(alias=settings.access_token_cookie)]

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


class PageAuthRequiredError(Exception):
    """Сторінка вимагає входу. Обробник у app/main.py віддає 302 на форму входу."""


def _load_user(session: Session, token: str) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний або протермінований токен",
            headers=UNAUTHORIZED_HEADERS,
        ) from exc

    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Обліковий запис недоступний",
            headers=UNAUTHORIZED_HEADERS,
        )
    return user


def get_optional_user(
    session: SessionDep,
    header_token: TokenFromHeader = None,
    cookie_token: TokenFromCookie = None,
) -> User | None:
    """Користувач, якщо він автентифікований. Інакше None."""
    token = header_token or cookie_token
    if token is None:
        return None
    return _load_user(session, token)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(
    session: SessionDep,
    header_token: TokenFromHeader = None,
    cookie_token: TokenFromCookie = None,
) -> User:
    """Обов'язкова автентифікація для REST-маршрутів: без токена — 401."""
    token = header_token or cookie_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Потрібна автентифікація",
            headers=UNAUTHORIZED_HEADERS,
        )
    return _load_user(session, token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """Вертикальне розмежування: маршрут лише для адміністратора."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ лише для адміністратора",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_page_user(
    session: SessionDep,
    cookie_token: TokenFromCookie = None,
) -> User:
    """Обов'язкова автентифікація для HTML-сторінок: без cookie — перенаправлення."""
    if cookie_token is None:
        raise PageAuthRequiredError
    return _load_user(session, cookie_token)


PageUser = Annotated[User, Depends(get_page_user)]
