"""Операції з обліковими записами."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.services.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)

# Однакове повідомлення для неіснуючого email і невірного пароля: інакше форма
# входу перетворюється на інструмент перевірки, чи зареєстрований користувач.
INVALID_CREDENTIALS = "Невірний email або пароль"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.PASSENGER,
) -> User:
    """Створити обліковий запис.

    Унікальність email перевіряється двічі: запитом (щоб віддати зрозумілу
    помилку) і обмеженням бази (щоб два паралельні запити не створили дублікат).
    """
    normalized = normalize_email(email)

    if session.scalar(select(User.id).where(User.email == normalized)) is not None:
        raise ConflictError("Користувач з таким email вже існує")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Користувач з таким email вже існує") from exc

    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    """Перевірити пару email/пароль."""
    user = session.scalar(select(User).where(User.email == normalize_email(email)))

    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not user.is_active:
        raise AuthenticationError("Обліковий запис деактивований")

    return user


def update_profile(session: Session, actor: User, user_id: int, full_name: str) -> User:
    """Змінити профіль.

    Горизонтальне розмежування: пасажир редагує лише власний профіль. Перевірка
    прав виконується до перевірки існування запису, щоб не підтверджувати
    сторонньому користувачу наявність чужого ідентифікатора.
    """
    if not actor.is_admin and actor.id != user_id:
        raise PermissionDeniedError("Можна змінювати лише власний профіль")

    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("Користувача не знайдено")

    user.full_name = full_name.strip()
    session.commit()
    session.refresh(user)
    return user
