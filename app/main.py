"""Точка входу застосунку.

Застосунок навмисно залишений stateless: жоден стан запиту не тримається в пам'яті
процесу. Це дозволить у наступних роботах запустити кілька однакових екземплярів
за балансувальником без змін у коді.
"""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Платформа продажу квитків на міжміські автобуси: динамічний розклад "
        "та блокування місць під час транзакції."
    ),
    debug=settings.debug,
)

app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["service"], summary="Коротка інформація про сервіс")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
