"""Реєстрація, вхід та профіль користувача."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenRead,
    UserRead,
)
from app.services import users as users_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User, response: Response) -> TokenRead:
    """Видати токен і продублювати його в cookie для HTML-сторінок."""
    token = create_access_token(user_id=user.id, role=user.role.value)
    max_age = settings.access_token_expire_minutes * 60

    response.set_cookie(
        key=settings.access_token_cookie,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return TokenRead(access_token=token, expires_in=max_age)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Реєстрація пасажира",
)
def register(payload: RegisterRequest, session: SessionDep) -> User:
    return users_service.create_user(
        session,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )


@router.post("/login", response_model=TokenRead, summary="Вхід (форма OAuth2)")
def login(
    response: Response,
    session: SessionDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenRead:
    """Вхід через стандартну форму OAuth2.

    Поле username містить email. Такий формат дозволяє користуватися кнопкою
    Authorize у Swagger UI без окремого клієнта.
    """
    user = users_service.authenticate(session, form.username, form.password)
    return _issue_token(user, response)


@router.post("/login/json", response_model=TokenRead, summary="Вхід (JSON)")
def login_json(payload: LoginRequest, response: Response, session: SessionDep) -> TokenRead:
    user = users_service.authenticate(session, payload.email, payload.password)
    return _issue_token(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Вихід")
def logout(response: Response) -> None:
    response.delete_cookie(settings.access_token_cookie)


@router.get("/me", response_model=UserRead, summary="Власний профіль")
def read_me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserRead, summary="Змінити власний профіль")
def update_me(payload: ProfileUpdateRequest, user: CurrentUser, session: SessionDep) -> User:
    return users_service.update_profile(
        session,
        actor=user,
        user_id=user.id,
        full_name=payload.full_name,
    )
