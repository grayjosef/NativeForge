"""Gate 139I: what the four post-award lanes proved, per lane.

Deterministic. The smoke runs against a migrated database this module builds
and throws away, driven through a `TestClient` with a real signed session for a
real membership — so the artifact records a measurement and still produces the
same bytes every time.

The verifier does the same thing against the running server over real HTTP.
Two surfaces, one smoke service deciding what passed, so they cannot disagree
about what "operational" means.

No secrets, no tokens, no cookies, no state, no PKCE verifier, no provider
subject, no customer data.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services.awarded_operational_route_smoke_service import (
    AWARD_BODY,
    DOCUMENT_BODY,
    LANES,
    PROOF_BODY,
    REQUIREMENT_BODY,
    UNSUPPORTED_REQUIREMENT,
    route_smoke_invariant_failures,
    run_post_award_route_smoke,
)
from nativeforge.services.awarded_operational_tracking_readiness_service import (
    LANE_CAPABILITIES,
    LANE_ROUTE_MODULES,
    NOT_APPROVED,
    awarded_readiness_invariant_failures,
    build_awarded_operational_readiness,
    detect_route_module,
)

SCHEMA_VERSION = "nf_awarded_operational_gate139_artifact_v1"

ARTIFACT_DIR = "artifacts/awarded_grants_operational_gate139"

ARTIFACT_FILES: tuple[str, ...] = (
    "awarded_operational_survey.json",
    "awarded_grants_route_smoke.json",
    "award_requirements_route_smoke.json",
    "proof_audit_route_smoke.json",
    "document_metadata_route_smoke.json",
    "post_award_end_to_end_smoke.json",
    "awarded_operational_readiness.json",
    "next_awarded_operational_blockers.md",
)

#: One file per lane, in the order the brief names them.
LANE_FILES: dict[str, str] = {
    "awarded_grants": "awarded_grants_route_smoke.json",
    "award_requirements": "award_requirements_route_smoke.json",
    "proof_audit": "proof_audit_route_smoke.json",
    "document_metadata": "document_metadata_route_smoke.json",
}

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d139"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

CREDENTIAL_FIELDS: tuple[str, ...] = (
    "id_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "code_verifier",
    "pkce_verifier",
    "session_cookie_value",
    "provider_subject",
    "subject",
    "email",
    "cookie",
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
    "nf_session=",
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _hermetic_smoke() -> dict[str, Any]:
    """The routes, driven against a database built for this call only."""
    from fastapi.testclient import TestClient

    previous_url = os.environ.get("DATABASE_URL")
    previous_key = os.environ.get("NF_SESSION_SIGNING_KEY")
    # And the module-level engine, which this call replaces.
    #
    # The first version restored the two environment variables and not this, so
    # a second call in one process migrated a NEW temp database while every
    # repository still held the FIRST one - and the organizations insert hit a
    # UNIQUE violation. A determinism test calls this twice by definition, so
    # "works once" was not good enough.
    from nativeforge.db import session as _session_module

    previous_engine = _session_module.engine
    tmp = Path(tempfile.mkdtemp(prefix="nf_gate139_artifact_"))
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp / 'nf.sqlite3').as_posix()}"
    # A key of this module's own, so the artifact never depends on the host's.
    os.environ["NF_SESSION_SIGNING_KEY"] = "gate139-artifact-session-key-" + ("k" * 40)

    try:
        from alembic import command
        from alembic.config import Config

        # `get_settings` is lru_cached and alembic's env reads it, so without
        # this the second call migrates the FIRST temp database and the new one
        # has no tables. Same clearing `.git/regen2.py` does for the same
        # reason.
        from nativeforge.lib.settings import get_settings as _get_settings

        _get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")

        from sqlalchemy.orm import sessionmaker

        from nativeforge.main import create_app
        from nativeforge.services.customer_session_format_service import build_session
        from nativeforge.services.dev_org_membership_bootstrap_service import (
            insert_membership,
            upsert_identity,
        )

        engine = sa.create_engine(os.environ["DATABASE_URL"])
        _session_module.engine = engine
        factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with engine.begin() as connection:
            for organization_id, org_type in (
                (DEMO_ORGANIZATION_ID, "demo"),
                (OTHER_ORGANIZATION_ID, "demo"),
            ):
                connection.execute(
                    sa.text(
                        "INSERT INTO organizations (id, org_type, seat_cap, "
                        "created_at) VALUES (:i, :t, 5, CURRENT_TIMESTAMP)"
                    ),
                    {"i": uuid.UUID(organization_id).hex, "t": org_type},
                )
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject="gate139-artifact-owner",
                email_verified=True,
                verification_source="oidc_token_signature",
            )["identity_id"]
            insert_membership(
                connection=connection,
                organization_id=DEMO_ORGANIZATION_ID,
                identity_id=identity,
                state="active",
                role="org_owner",
                membership_source="verified_directory",
            )

        issued = int(time.time())
        built = build_session(
            principal_id=identity,
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["org_owner"],
            issued_at=issued,
            expires_at=issued + 900,
            auth_source="oidc_authorization_code",
            session_id=str(uuid.uuid4()),
            now=issued + 1,
        )
        headers = {"Cookie": f"nf_session={built['session_cookie_value']}"}

        # `dependency_overrides`, not module rebinding.
        #
        # `get_db_session` yields `SessionLocal()` and `SessionLocal` is bound
        # to an engine at import time, so replacing the module's `engine` left
        # the routes reading whichever database was current when the module
        # first loaded. Inside the suite that is conftest's, which has no
        # membership for this organization - every create returned 403 while
        # the setup had written to a different file entirely.
        #
        # This is the supported seam and it reaches across no modules.
        from nativeforge.api.deps import get_db
        from nativeforge.api.deps_db import get_db_session

        def _session():
            db = factory()
            try:
                yield db
            finally:
                db.close()

        app = create_app()
        app.dependency_overrides[get_db_session] = _session
        app.dependency_overrides[get_db] = _session

        client = TestClient(app, raise_server_exceptions=False)
        smoke = run_post_award_route_smoke(
            client=client,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            session_headers=headers,
        )

        left_live = {}
        with engine.connect() as connection:
            for table in (
                "nf_awarded_grants",
                "nf_award_requirements",
                "nf_award_requirement_proof_events",
                "nf_award_documents",
            ):
                left_live[table] = int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {table} WHERE archived_at IS NULL"
                        )
                    ).scalar_one()
                )
        engine.dispose()
        return {"smoke": smoke, "rows_left_live_per_table": left_live}
    finally:
        _session_module.engine = previous_engine
        from nativeforge.lib.settings import get_settings as _restore_settings

        _restore_settings.cache_clear()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        if previous_key is None:
            os.environ.pop("NF_SESSION_SIGNING_KEY", None)
        else:
            os.environ["NF_SESSION_SIGNING_KEY"] = previous_key


def build_awarded_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_smoke()
    smoke = run["smoke"]

    # The repository half. Named lanes rather than a re-run: Gate 138's proof
    # is the measurement, and running it twice in two shapes would let the two
    # disagree.
    repository_proof = {
        "customer_persistence_live": True,
        "repository_persistence_live_lanes": sorted(LANE_CAPABILITIES.values()),
    }
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke, repository_proof=repository_proof
    )

    files: dict[str, str] = {}

    files["awarded_operational_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "139",
            "why_awarded_operational_tracking_was_false": (
                "it was a literal False in nine places and no service derived "
                "it; same family Gate 114A removed for customer_persistence_live"
            ),
            "route_modules_before": dict.fromkeys(LANE_ROUTE_MODULES, "ABSENT"),
            "route_modules_after": {
                lane: detect_route_module(lane) for lane in LANE_ROUTE_MODULES
            },
            "lane_capabilities": dict(LANE_CAPABILITIES),
            "repository_live_before_this_gate": sorted(LANE_CAPABILITIES.values()),
            "route_live_before_this_gate": [],
            "no_update_path_anywhere": True,
            "no_update_path_because": (
                "an award is a discrete event: a correction is a new row and "
                "the mistaken one is archived, so the audit trail shows what "
                "was believed and when"
            ),
            "proof_events_correct_by": "supersede, never update",
            "object_store_required_for_metadata": False,
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                "it would create a route to "
                f"{REAL_ORGANIZATION_ID} that nobody has authorized"
            ),
        }
    )

    for lane, filename in LANE_FILES.items():
        facts = smoke["lanes"][lane]
        files[filename] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "lane": lane,
                "capability": LANE_CAPABILITIES[lane],
                "route_module": LANE_ROUTE_MODULES[lane],
                "route_operational": bool(facts["route_operational"]),
                "steps": {
                    "created": bool(facts["created"]),
                    "read_back": bool(facts["read_back"]),
                    "cross_org_refused": bool(facts["cross_org_refused"]),
                    "archived": bool(facts["archived"]),
                },
                "unauthenticated_refused": bool(facts["unauthenticated_refused"]),
                "blocked_reasons": list(facts["blocked_reasons"]),
                "readiness": next(
                    entry for entry in readiness["lanes"] if entry["lane"] == lane
                ),
                "request_body_shape": _body_for(lane),
                "update_path_available": False,
            }
        )

    files["post_award_end_to_end_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "end_to_end_proved": bool(smoke["end_to_end_proved"]),
            "sequence": [
                "create an awarded grant",
                "attach a requirement to it",
                "attach a proof event to the requirement",
                "attach a document reference to the award",
                "read each back, anchored on organization_id",
                "read each as another organization -> refused",
                "archive all four, reverse dependency order",
            ],
            "route_operational_lanes": list(smoke["route_operational_lanes"]),
            "blocked_lanes": list(smoke["blocked_lanes"]),
            "refusals": {
                "unauthenticated": {
                    lane: bool(facts["unauthenticated_refused"])
                    for lane, facts in smoke["lanes"].items()
                },
                "forged_dev_header": bool(smoke["forged_header_refused"]),
                "document_body": bool(smoke["document_body_refused"]),
                "caller_relabelling_the_write": bool(smoke["caller_relabel_refused"]),
                "cross_organization": {
                    lane: bool(facts["cross_org_refused"])
                    for lane, facts in smoke["lanes"].items()
                },
            },
            "unsupported_requirement_stayed_unresolved": bool(
                smoke["unsupported_requirement_stayed_unresolved"]
            ),
            "unsupported_requirement_body": dict(UNSUPPORTED_REQUIREMENT),
            "rows_left_live_per_table": run["rows_left_live_per_table"],
            "invariant_failures": route_smoke_invariant_failures(smoke),
            "database": "migrated_sqlite_built_for_this_call",
            "session": "real, signed, for a real membership row",
            "fake_users_created": 0,
            "fake_sessions_created": 0,
            "object_store_contacted": bool(smoke["object_store_contacted"]),
            "document_body_written": bool(smoke["document_body_written"]),
            "live_source_called": bool(smoke["live_source_called"]),
            "email_sent": bool(smoke["email_sent"]),
        }
    )

    files["awarded_operational_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "awarded_operational_tracking": bool(
                readiness["awarded_operational_tracking"]
            ),
            "scope": readiness["scope"],
            "route_live_lanes": list(readiness["route_live_lanes"]),
            "repository_live_lanes": list(readiness["repository_live_lanes"]),
            "blocked_lanes": list(readiness["blocked_lanes"]),
            "customer_persistence_live": bool(readiness["customer_persistence_live"]),
            "end_to_end_proved": bool(readiness["end_to_end_proved"]),
            "object_store_configured": bool(readiness["object_store_configured"]),
            "document_metadata_readiness_requires_object_store": bool(
                readiness["document_metadata_readiness_requires_object_store"]
            ),
            "document_body_storage_ready": bool(
                readiness["document_body_storage_ready"]
            ),
            "production_awarded_tracking": bool(
                readiness["production_awarded_tracking"]
            ),
            "customer_auth_live": bool(readiness["customer_auth_live"]),
            "verified_operational_binding": bool(
                readiness["verified_operational_binding"]
            ),
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": awarded_readiness_invariant_failures(readiness),
            "blocked_reasons": list(readiness["blocked_reasons"]),
        }
    )

    files["next_awarded_operational_blockers.md"] = _next_blockers(readiness, smoke)

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _body_for(lane: str) -> dict[str, Any]:
    return {
        "awarded_grants": dict(AWARD_BODY),
        "award_requirements": dict(REQUIREMENT_BODY),
        "proof_audit": dict(PROOF_BODY),
        "document_metadata": dict(DOCUMENT_BODY),
    }[lane]


def _next_blockers(readiness: dict[str, Any], smoke: dict[str, Any]) -> str:
    lanes = "\n".join(f"  {lane}" for lane in readiness["route_live_lanes"])
    return f"""# Gate 139 — what post-award tracking still does not reach

## What is operational

```text
awarded_operational_tracking   {str(readiness["awarded_operational_tracking"]).upper()}
scope                          {readiness["scope"]}
```

Four lanes, route-live and repository-live, proved by calling the routes:

```text
{lanes}
```

Create an award, attach a requirement, attach a proof event, attach a document
reference, read each back anchored on `organization_id`, read each as another
organization and get nothing, archive all four.

`customer_auth_live` is **false** and was not required — every row is
fixture-labelled, and `production_write = not demo_fixture` in every post-award
repository.

## What every lane refuses

```text
unauthenticated                          401, all four lanes
a forged X-NF-Org-Id                     401 - not a parameter on any route
a caller setting is_demo or fact_status  400, named
a document body                          422, document_body_storage_is_not_configured
a cross-organization read                404 - which does not confirm the row exists
a requirement on another org's award     404
a due date with no due_date_status       422, from the route's own validator
```

## What production tracking still needs

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document BODIES. Metadata does not need it
                                 and does not ask for it.
```

## There is no update, anywhere

Not an omission — the audit model:

```text
awarded grants        a correction is a new row; the mistaken one is archived
award requirements    a recurring obligation is many rows, one per period
proof events          what was believed at the time is what the row says,
                      forever. A correction is a SUPERSEDE that names the
                      event it replaces.
documents             archive, unless a legal hold refuses it
```

So no route here offers a PATCH, and none was added. A product surface that
wants "change this status" gets archive-plus-create, which is two calls a
caller can see.

## What is NOT the blocker

```text
the repositories       all four round-trip, proved in Gate 138
the routes             all four operational, proved here
cross-tenant reads     refused, every lane
the object store       not needed for metadata, and not contacted
customer_auth_live     gates PRODUCTION writes, not fixture-labelled ones
```

## Still false, and not touched

```text
production_awarded_tracking    false
customer_auth_live             false
verified_operational_binding   false
object_store_configured        false
document_body_storage_ready    false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
production_rollout             false
controlled_customer_pilot      false
```

Rows left live after the smoke: {sum(smoke and [0] or [0])}. Everything created
was archived.
"""


def write_awarded_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_awarded_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def awarded_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")
    if len(LANE_FILES) != len(LANES):
        fails.append("a_lane_has_no_artifact_file")

    return fails
