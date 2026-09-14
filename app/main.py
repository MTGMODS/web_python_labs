"""Точка входу застосунку.

Застосунок навмисно залишений stateless: жоден стан запиту не тримається в пам'яті
процесу. Це дозволить у наступних роботах запустити кілька однакових екземплярів
за балансувальником без змін у коді.
"""

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.deps import PageAuthRequiredError
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.services.exceptions import DomainError
from app.web import routes as web_routes

app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "Платформа продажу квитків на міжміські автобуси: динамічний розклад "
        "та блокування місць під час транзакції."
    ),
    debug=settings.debug,
    docs_url=None,
    redoc_url=None,
)

app.include_router(health_router)
app.include_router(web_routes.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
    name="static",
)


def _login_redirect_target(request: Request) -> str:
    """Після входу не відправляємо на POST-only URL, а на сторінку, з якої прийшли."""
    path = request.url.path
    if request.method == "GET" and path not in {web_routes.LOGIN_URL, "/register"}:
        return path
    parts = path.split("/")
    if len(parts) >= 3 and parts[1] == "trips":
        return f"/trips/{parts[2]}"
    if path.startswith("/admin"):
        return web_routes.ADMIN_HOME_URL
    return web_routes.PASSENGER_HOME_URL


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError) -> Response:
    """Єдине перетворення порушення бізнес-правила у код відповіді."""
    if request.url.path.startswith(settings.api_v1_prefix):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return RedirectResponse(
        f"{request.url.path}?error={quote(exc.detail)}",
        status_code=303,
    )


@app.exception_handler(PageAuthRequiredError)
def handle_page_auth_required(request: Request, exc: PageAuthRequiredError) -> Response:
    """Анонімний доступ до захищеної сторінки — перенаправлення на форму входу."""
    del exc
    return RedirectResponse(
        f"{web_routes.LOGIN_URL}?next={_login_redirect_target(request)}",
        status_code=302,
    )
