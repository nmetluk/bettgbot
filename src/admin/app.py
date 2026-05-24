"""FastAPI admin app (TASK-019).

Скелет веб-админки: статика, Jinja2-шаблоны, healthcheck. Auth/CSRF/middleware
появятся в TASK-020+, бизнес-роуты — в TASK-021+.

Запуск:
    uv run uvicorn src.admin.app:app --reload --host 127.0.0.1 --port 8000
или `make admin`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.shared.config import get_settings
from src.shared.logging import configure_logging, get_logger

__all__ = ["app", "templates"]


logger = get_logger(__name__)

_BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level, s.log_format)

    app = FastAPI(
        title="Betting Bot Admin",
        version="0.0.0",
        # OpenAPI docs не нужен для админки — выключаем, чтобы не было сюрпризов
        # на проде, где /docs/ доступен публично без auth.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(_BASE_DIR / "static")),
        name="static",
    )

    # Локальный импорт — избегаем circular (routes импортируют `templates` отсюда).
    from .routes import dashboard as dashboard_routes
    from .routes import login as login_routes

    app.include_router(login_routes.router)
    app.include_router(dashboard_routes.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("admin.startup")
    return app


app = create_app()
