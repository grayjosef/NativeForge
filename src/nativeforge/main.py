"""FastAPI application factory."""

from fastapi import FastAPI

from nativeforge.api.health import router as health_router
from nativeforge.api.isolation_routes import router as isolation_router
from nativeforge.lib.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router)
    app.include_router(isolation_router)
    return app


app = create_app()
