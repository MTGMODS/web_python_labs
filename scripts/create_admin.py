"""Створення адміністратора.

Запуск: python -m scripts.create_admin [email] [пароль] ["Ім'я Прізвище"]

Адміністратори створюються лише цим скриптом. Реєстрація з роллю ADMIN через
публічний API свідомо відсутня: інакше будь-хто міг би підвищити собі права.
"""

import sys

from app.core.config import settings
from app.db.session import SessionFactory
from app.models.user import UserRole
from app.services import users as users_service
from app.services.exceptions import DomainError


def main(argv: list[str]) -> int:
    email = argv[0] if len(argv) > 0 else settings.admin_email
    password = argv[1] if len(argv) > 1 else settings.admin_password
    full_name = argv[2] if len(argv) > 2 else "Адміністратор перевізника"

    with SessionFactory() as session:
        try:
            user = users_service.create_user(
                session,
                email=email,
                password=password,
                full_name=full_name,
                role=UserRole.ADMIN,
            )
        except DomainError as exc:
            print(f"Не створено: {exc.detail}")
            return 1

    print(f"Створено адміністратора {user.email} (id={user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
