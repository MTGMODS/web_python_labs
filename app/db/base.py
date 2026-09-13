"""Базові класи та спільні типи для моделей SQLAlchemy."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Єдині правила імен обмежень та індексів. Без них автогенеровані міграції
# створюють різні імена на різних середовищах, і відкат стає ненадійним.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Спільний декларативний клас. Його метадані використовує Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# На PostgreSQL схема салону зберігається як JSONB (індексується, компактніша),
# на інших діалектах — як звичайний JSON.
JsonColumn = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    """Часові мітки створення та останньої зміни запису."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
