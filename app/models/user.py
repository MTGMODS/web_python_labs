"""Користувачі системи та їхні ролі."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class UserRole(enum.StrEnum):
    """Роль визначає вертикальний рівень доступу.

    PASSENGER — клієнт: купує квитки й бачить лише свої.
    ADMIN — співробітник перевізника: керує розкладом і бачить усі квитки.
    """

    PASSENGER = "passenger"
    ADMIN = "admin"


user_role_enum = Enum(
    UserRole,
    name="user_role",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class User(Base, TimestampMixin):
    """Обліковий запис.

    Пароль зберігається виключно як bcrypt-хеш, тому колонка називається
    password_hash — щоб у коді не виникало спокуси покласти туди відкритий текст.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum,
        default=UserRole.PASSENGER,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tickets: Mapped[list[Ticket]] = relationship(back_populates="user")

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User {self.email} {self.role.value}>"
