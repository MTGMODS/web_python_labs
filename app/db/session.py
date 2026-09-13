"""Підключення до бази даних та фабрика сесій."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_pre_ping перевіряє з'єднання перед видачею з пулу: потрібно, бо у наступних
# роботах між застосунком і базою з'явиться балансувальник/пулер з'єднань.
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=settings.db_echo,
)

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Залежність FastAPI: сесія на один HTTP-запит."""
    with SessionFactory() as session:
        yield session
