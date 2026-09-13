"""Помилки бізнес-правил.

Сервісний шар не знає про HTTP і не піднімає HTTPException — він повідомляє про
порушення правила предметної області. Перетворення у код відповіді відбувається
в одному місці (обробник у app/main.py), тому API та веб-сторінки реагують на ту
саму помилку узгоджено.
"""

from fastapi import status


class DomainError(Exception):
    """Базове порушення бізнес-правила."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthenticationError(DomainError):
    """Не вдалося підтвердити особу користувача."""

    status_code = status.HTTP_401_UNAUTHORIZED


class PermissionDeniedError(DomainError):
    """Особа підтверджена, але прав на дію недостатньо."""

    status_code = status.HTTP_403_FORBIDDEN


class NotFoundError(DomainError):
    """Сутність предметної області відсутня."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """Дія суперечить поточному стану даних (місце вже зайняте тощо)."""

    status_code = status.HTTP_409_CONFLICT
