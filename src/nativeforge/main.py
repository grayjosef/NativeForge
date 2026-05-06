"""FastAPI application factory."""

from fastapi import FastAPI

from nativeforge.api.form_package_routes import (
    demo_form_pkg_router,
    real_form_pkg_router,
)
from nativeforge.api.grant_spark_routes import (
    demo_grant_spark_router,
    real_grant_spark_router,
)
from nativeforge.api.health import router as health_router
from nativeforge.api.isolation_routes import router as isolation_router
from nativeforge.api.nofo_extraction_routes import demo_nofo_router, real_nofo_router
from nativeforge.api.pursuit_brief_routes import (
    demo_pursuit_brief_router,
    real_pursuit_brief_router,
)
from nativeforge.api.pursuit_routes import demo_pursuit_router, real_pursuit_router
from nativeforge.api.spark_scoring_routes import (
    demo_spark_scoring_router,
    real_spark_scoring_router,
)
from nativeforge.api.sprint0_routes import demo_router, real_router
from nativeforge.api.tribal_profile_routes import (
    demo_profile_router,
    real_profile_router,
)
from nativeforge.api.trust_routes import demo_trust_router, real_trust_router
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
    app.include_router(demo_spark_scoring_router)
    app.include_router(real_spark_scoring_router)
    app.include_router(demo_pursuit_router)
    app.include_router(real_pursuit_router)
    app.include_router(demo_pursuit_brief_router)
    app.include_router(real_pursuit_brief_router)
    app.include_router(demo_form_pkg_router)
    app.include_router(real_form_pkg_router)
    app.include_router(demo_trust_router)
    app.include_router(real_trust_router)
    return app


app = create_app()
