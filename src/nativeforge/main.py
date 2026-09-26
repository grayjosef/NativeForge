"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from nativeforge.api.activation_routes import (
    demo_activation_router,
    real_activation_router,
)
from nativeforge.api.audit_replay_routes import (
    router as audit_replay_router,
)
from nativeforge.api.auth import install_auth_security_scheme
from nativeforge.api.auth import router as auth_router

# Gate 139. The four post-award lanes, demo-scoped.
#
# There is deliberately no real-organization counterpart: building one would
# create a route to aaaaaaaa-… that nobody has authorized, and Gate 137's
# activation boundary exists precisely because that authorization does not.
from nativeforge.api.award_document_routes import router as award_document_router
from nativeforge.api.award_requirement_proof_routes import (
    router as award_proof_router,
)
from nativeforge.api.award_requirements_routes import (
    router as award_requirements_router,
)
from nativeforge.api.awarded_grants_routes import router as awarded_grants_router
from nativeforge.api.backend_runtime_routes import router as backend_runtime_router
from nativeforge.api.beta_onboarding_cockpit_routes import (
    router as beta_cockpit_router,
)
from nativeforge.api.controlled_beta_readiness_routes import (
    router as controlled_beta_router,
)
from nativeforge.api.controlled_customer_pilot_routes import (
    router as controlled_customer_pilot_router,
)
from nativeforge.api.customer_auth_readiness_routes import (
    router as customer_auth_readiness_router,
)
from nativeforge.api.customer_beta_reassessment_routes import (
    router as customer_beta_reassessment_router,
)
from nativeforge.api.customer_data_boundary_routes import (
    router as customer_data_boundary_router,
)
from nativeforge.api.digest_delivery_routes import (
    router as digest_delivery_router,
)
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
from nativeforge.api.operational_backup_routes import (
    router as operational_backup_router,
)
from nativeforge.api.operational_durability_reassessment_routes import (
    router as durability_reassessment_router,
)
from nativeforge.api.operational_health_routes import (
    router as operational_health_router,
)
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
from nativeforge.api.source_authorization_routes import (
    router as source_authorization_router,
)
from nativeforge.api.source_collection_job_store_routes import (
    router as source_job_store_router,
)
from nativeforge.api.source_collection_orchestration_routes import (
    router as source_orchestration_router,
)
from nativeforge.api.source_collection_scheduler_routes import (
    router as source_scheduler_router,
)
from nativeforge.api.source_collection_worker_routes import (
    router as source_worker_router,
)
from nativeforge.api.source_collector_execution_routes import (
    router as source_collector_execution_router,
)
from nativeforge.api.source_ingestion_routes import (
    demo_source_ingestion_router,
    real_source_ingestion_router,
)
from nativeforge.api.source_monitoring_readiness_routes import (
    router as source_monitoring_router,
)
from nativeforge.api.source_raw_payload_routes import (
    router as source_raw_payload_router,
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
from nativeforge.api.tenant_digest_persistence_routes import (
    router as tenant_digest_persistence_router,
)
from nativeforge.api.tenant_digest_routes import router as tenant_digest_router
from nativeforge.api.tenant_watchlist_routes import (
    router as tenant_watchlist_router,
)
from nativeforge.api.tribal_profile_routes import (
    demo_profile_router,
    real_profile_router,
)
from nativeforge.api.trust_routes import demo_trust_router, real_trust_router
from nativeforge.api.verified_binding_readiness_routes import (
    router as verified_binding_readiness_router,
)
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
    app.include_router(awarded_grants_router)
    app.include_router(award_requirements_router)
    app.include_router(award_proof_router)
    app.include_router(award_document_router)
    # Gate 140: the source watchlist and the matched-NOFO digest, behind an
    # authenticated demo organization context. Neither calls a live source;
    # neither sends mail.
    app.include_router(tenant_watchlist_router)
    app.include_router(tenant_digest_router)
    # Gate 151: the digest a delivery intent names, stored and readable back.
    # Nothing here sends, renders to a stored body, or keeps a recipient.
    app.include_router(tenant_digest_persistence_router)
    # Gate 152: audit replay and the evidence ledger. GET only - a replay
    # reads, fabricates nothing, and reports legacy gaps rather than filling
    # them.
    app.include_router(audit_replay_router)
    # Gate 153: the backup manifest, export accounting and the restore lane.
    # GET only, and no route returns the exported rows - an export exists to
    # be handed to a restore, not to a browser.
    app.include_router(operational_backup_router)
    # Gate 154: operational health, the verifier registry and the runbook.
    # GET only, and no route shells out - a health route that ran systemctl
    # would be a command execution surface reachable with a session cookie.
    app.include_router(operational_health_router)
    # Gate 155: the durability reassessment and the next-activation decision.
    # GET only. Nothing here activates a capability or changes a lane - a
    # reassessment that could change what it reassesses would not be one.
    app.include_router(durability_reassessment_router)
    # Gate 156: the source scheduler runtime. It evaluates a schedule and
    # refuses every source; no route can dispatch, fetch or approve anything,
    # and source_monitoring_live is a constant false.
    app.include_router(source_scheduler_router)
    # Gate 157: the source collection worker. It claims jobs and refuses every
    # one; no route claims a lease, and source_monitoring_live is constant.
    app.include_router(source_worker_router)
    app.include_router(source_job_store_router)
    # Gate 159: the periodic orchestration runtime. GET routes report the
    # trigger, the missed-window state and the lane; the POST runs a full
    # cycle inside a SAVEPOINT and rolls it back, so a read endpoint
    # cannot consume the real slot and suppress the next genuine cycle.
    app.include_router(source_orchestration_router)
    # Gate 160: the raw payload spine. GET routes report the lane and
    # replay stored bytes as base64; the POST persists a FIXED synthetic
    # fixture inside a SAVEPOINT and rolls it back. No route accepts
    # caller bytes and no route fetches a URL.
    app.include_router(source_raw_payload_router)
    # Gate 161: the collector execution envelope. Two reads and one smoke
    # that runs the whole envelope against a REGISTERED FIXTURE inside a
    # SAVEPOINT and rolls it back. No route takes a URL - not as a
    # parameter, not as a default, not as an allowlist a caller selects
    # from - so there is no address a caller could point it at.
    app.include_router(source_collector_execution_router)
    # Gate 162: the recorded source authorization boundary. FOUR READS and no
    # writes - no route approves a source, records a terms decision, records a
    # human review, flips an allowlist entry or executes anything. Every value
    # is resolved from records; no route accepts a fact.
    app.include_router(source_authorization_router)
    # Gate 142: digest delivery, rehearsed. Nothing here sends mail and no
    # provider is contacted.
    app.include_router(digest_delivery_router)
    # Gate 143: source monitoring readiness. Nothing here fetches a source
    # and no collector is started.
    app.include_router(source_monitoring_router)
    # Gate 144: the beta onboarding cockpit. Reports the deployment's own
    # readiness; activates nothing and names no customer.
    app.include_router(beta_cockpit_router)
    # Gate 145: the controlled beta decision matrix. Reports a decision;
    # approves nothing and activates nothing.
    app.include_router(controlled_beta_router)
    # Gate 146: the second-person invite checklist. Read-only by design - there
    # is no POST here, because issuing and accepting an invite are the two
    # operator commands Gate 136 built and neither belongs one request away
    # from anybody holding a session.
    app.include_router(customer_auth_readiness_router)
    # Gate 147: the verified-binding approval boundary. Its one POST evaluates
    # a hypothetical approval and records nothing - the mutation path stays
    # where Gate 137 put it, behind an approval object that does not exist.
    app.include_router(verified_binding_readiness_router)
    # Gate 148: the consent and customer data boundary. Its one POST evaluates
    # a hypothetical write and records nothing - no consent, no approval, no
    # row. Customer data writes are refused; demo fixtures are unaffected.
    app.include_router(customer_data_boundary_router)
    # Gate 149: the controlled customer pilot activation package. Its one POST
    # decides and records nothing - there is no table, no flag and no code path
    # that activates a pilot, and this gate deliberately builds none.
    app.include_router(controlled_customer_pilot_router)
    # Gate 150: the customer beta reassessment. GET only - it compares two
    # decisions and reports the difference, which today is none.
    app.include_router(customer_beta_reassessment_router)
    app.include_router(auth_router)
    install_auth_security_scheme(app)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built frontend from the same origin, if one is bundled.

    Mounted last, and only last. A mount at `/` is a catch-all: registered
    before the routers it would shadow every API path in the application.

    Same-origin is a deliberate portability choice rather than a convenience.
    Split across two services the frontend needs to be told the API's address,
    and `apiFetchBase()` falls back to `http://127.0.0.1:8000` when nothing
    tells it - so a deployed page probes the *viewer's* own machine, which
    cannot succeed and is mixed content on an HTTPS page. Served from one
    origin the requests are relative, there is no CORS, no second hostname,
    and the image is not bound to the domain it happens to be running under.

    Absent directory means no frontend bundled, which is how the test suite
    and the SQLite development lane run; `html=True` serves index.html so
    client-side routes survive a refresh.
    """
    configured = get_settings().nf_frontend_dist
    if not configured:
        return
    dist = Path(configured)
    if not dist.is_dir():
        return
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")


app = create_app()
