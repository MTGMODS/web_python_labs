"""Хешування паролів та токени доступу.

Модуль не знає ні про базу даних, ні про HTTP: він лише перетворює пароль у хеш
і користувача у підписаний токен. Це дозволяє перевіряти його юніт-тестами та
замінити реалізацію (наприклад, на зовнішній провайдер) без правок в API.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# Обмеження алгоритму bcrypt: він враховує лише перші 72 байти пароля.
PASSWORD_MAX_BYTES = 72


class InvalidTokenError(Exception):
    """Токен відсутній, підроблений або протермінований."""


def hash_password(password: str) -> str:
    """Створити хеш пароля з унікальною солью."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Порівняти пароль із хешем у сталий час."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Пошкоджений хеш у базі не має призводити до 500-ї помилки.
        return False


def create_access_token(user_id: int, role: str) -> str:
    """Підписаний токен доступу з ідентифікатором користувача та його роллю.

    Роль кладеться у токен свідомо: це дозволяє перевіряти доступ без запиту до
    бази на кожен HTTP-запит. Платою є затримка поширення зміни ролі — до
    закінчення терміну життя токена.
    """
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Перевірити підпис і термін дії токена."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
