"""Точка входу застосунку.

Застосунок навмисно залишений stateless: жоден стан запиту не тримається в пам'яті
процесу. Це дозволить у наступних роботах запустити кілька однакових екземплярів
за балансувальником без змін у коді.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.api.deps import PageAuthRequiredError
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.services.exceptions import DomainError
from app.web import routes as web_routes

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Платформа продажу квитків на міжміські автобуси: динамічний розклад "
        "та блокування місць під час транзакції."
    ),
    debug=settings.debug,
)

app.include_router(health_router)
app.include_router(web_routes.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError) -> Response:
    """Єдине перетворення порушення бізнес-правила у код відповіді.

    Завдяки цьому сервісний шар не залежить від HTTP, а API та сторінки
    реагують на ту саму помилку узгоджено.
    """
    del request
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(PageAuthRequiredError)
def handle_page_auth_required(request: Request, exc: PageAuthRequiredError) -> Response:
    """Анонімний доступ до захищеної сторінки — перенаправлення на форму входу."""
    del exc
    return RedirectResponse(
        f"{web_routes.LOGIN_URL}?next={request.url.path}",
        status_code=302,
    )


@app.get("/", tags=["service"], summary="Коротка інформація про сервіс")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
        "login": web_routes.LOGIN_URL,
    }
