"""FastAPI application factory."""

from fastapi import FastAPI

from nativeforge.api.grant_spark_routes import (
    demo_grant_spark_router,
    real_grant_spark_router,
)
from nativeforge.api.health import router as health_router
from nativeforge.api.isolation_routes import router as isolation_router
from nativeforge.api.nofo_extraction_routes import demo_nofo_router, real_nofo_router
from nativeforge.api.sprint0_routes import demo_router, real_router
from nativeforge.api.tribal_profile_routes import (
    demo_profile_router,
    real_profile_router,
)
from nativeforge.lib.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router)
    app.include_router(isolation_router)
    app.include_router(demo_router)
    app.include_router(real_router)
    app.include_router(demo_profile_router)
    app.include_router(real_profile_router)
    app.include_router(demo_grant_spark_router)
    app.include_router(real_grant_spark_router)
    app.include_router(demo_nofo_router)
    app.include_router(real_nofo_router)
    return app


app = create_app()
