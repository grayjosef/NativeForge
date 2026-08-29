"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from nativeforge.api.activation_routes import (
    demo_activation_router,
    real_activation_router,
)
from nativeforge.api.auth import install_auth_security_scheme
from nativeforge.api.auth import router as auth_router
from nativeforge.api.backend_runtime_routes import router as backend_runtime_router
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
from nativeforge.api.operator_workbench_advisory_routes import (
    demo_workbench_advisory_router,
    real_workbench_advisory_router,
)
from nativeforge.api.opportunity_discovery_routes import (
    demo_discovery_router,
    real_discovery_router,
)
from nativeforge.api.pursuit_brief_routes import (
    demo_pursuit_brief_router,
    real_pursuit_brief_router,
)
from nativeforge.api.pursuit_routes import demo_pursuit_router, real_pursuit_router
from nativeforge.api.source_ingestion_routes import (
    demo_source_ingestion_router,
    real_source_ingestion_router,
)
from nativeforge.api.spark_scoring_routes import (
    demo_spark_scoring_router,
    real_spark_scoring_router,
)
from nativeforge.api.sprint0_routes import demo_router, real_router
from nativeforge.api.stage12_guided_demo_routes import (
    demo_stage12_router,
    real_stage12_router,
)
from nativeforge.api.tribal_profile_routes import (
    demo_profile_router,
    real_profile_router,
)
from nativeforge.api.trust_routes import demo_trust_router, real_trust_router
from nativeforge.lib.settings import get_settings
from nativeforge.services.backend_lifespan_hook_service import (
    record_shutdown,
    record_startup,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gate 102C: the attach point a future in-process scheduler would use.

    Nothing is attached to it. Startup records that it ran and starts no
    scheduler, no collector, and no fetch; shutdown records that it ran and
    stops nothing, because nothing was running.

    The hook exists because Gates 100A and 101A both ended at the same wall -
    there was nowhere for an in-process background task to live even once a
    process existed. Adding the attach point removes that wall without stepping
    over it, and it makes the absence of a scheduler *testable*: "no scheduler
    runs at startup" used to be true because startup did not exist, and is now
    true because startup ran and deliberately started nothing.

    Anything attached here in a later gate must first satisfy
    `ATTACH_PREREQUISITES` in `backend_lifespan_hook_service` - a proven
    persistent backend, a background worker, a periodic trigger, and a
    production payload store. None is satisfied today.
    """
    record_startup()
    try:
        yield
    finally:
        record_shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(backend_runtime_router)
    app.include_router(isolation_router)
    app.include_router(demo_router)
    app.include_router(real_router)
    app.include_router(demo_profile_router)
    app.include_router(real_profile_router)
    app.include_router(demo_grant_spark_router)
    app.include_router(real_grant_spark_router)
    app.include_router(demo_discovery_router)
    app.include_router(real_discovery_router)
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
    app.include_router(demo_workbench_advisory_router)
    app.include_router(real_workbench_advisory_router)
    app.include_router(demo_stage12_router)
    app.include_router(real_stage12_router)
    app.include_router(demo_source_ingestion_router)
    app.include_router(real_source_ingestion_router)
    app.include_router(demo_activation_router)
    app.include_router(real_activation_router)
    # Gate 116: five customer auth routes that authenticate nobody and
    # say so. The security scheme is advertised and applied to no
    # operation - see api/auth.py.
    app.include_router(auth_router)
    install_auth_security_scheme(app)
    return app


app = create_app()
