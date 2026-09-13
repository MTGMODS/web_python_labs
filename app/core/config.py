"""Конфігурація застосунку.

Усі параметри читаються з оточення (файл .env у корені проєкту), тому один і той
самий образ застосунку можна запускати локально, у контейнері та за балансувальником
без зміни коду.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Bus Tickets Platform"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://bus_app:bus_app@localhost:5432/bus_tickets"
    test_database_url: str = "postgresql+psycopg://bus_app:bus_app@localhost:5432/bus_tickets_test"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # Автентифікація
    secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    access_token_cookie: str = "access_token"

    # Бізнес-правила
    seat_hold_minutes: int = 10

    # Початковий адміністратор для scripts/seed.py
    admin_email: str = "admin@bus.local"
    admin_password: str = "admin12345"


@lru_cache
def get_settings() -> Settings:
    """Кешований доступ до налаштувань: файл .env читається один раз за процес."""
    return Settings()


settings = get_settings()
