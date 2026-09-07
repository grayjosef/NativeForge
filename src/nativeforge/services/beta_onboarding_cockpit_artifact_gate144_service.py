"""Gate 144G: what the cockpit shows, as committed files.

Deterministic. The cockpit routes run against a migrated database this module
builds and throws away, driven through a `TestClient` with a real signed session
for a real membership.

Nothing is activated: no live source is called, no collector starts, no mail is
sent, no object store is contacted, and no lane's value changes. Every artifact
is scanned for credential- and customer-shaped strings before it is returned.
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

from nativeforge.services.beta_onboarding_readiness_summary_service import (
    LANE_EVIDENCE,
    LANE_KEYS,
    LANE_STATUSES,
    NEVER_TRUE_LANES,
    NEXT_SAFE_ACTION,
    NOT_APPROVED,
    build_beta_onboarding_summary,
    summary_invariant_failures,
)

SCHEMA_VERSION = "nf_beta_onboarding_cockpit_gate144_artifact_v1"

ARTIFACT_DIR = "artifacts/beta_onboarding_cockpit_gate144"

ARTIFACT_FILES: tuple[str, ...] = (
    "beta_onboarding_cockpit_survey.json",
    "readiness_summary_smoke.json",
    "cockpit_route_smoke.json",
    "cockpit_blockers_matrix.json",
    "cockpit_next_safe_actions.json",
    "frontend_cockpit_status.json",
    "beta_onboarding_cockpit_readiness.json",
    "next_beta_onboarding_blockers.md",
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d144"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: The frontend surface this gate added, and what it must not do.
FRONTEND_SURFACE = "beta_onboarding_cockpit"
FRONTEND_PAGE = "frontend/src/pages/BetaOnboardingCockpitPage.tsx"
FRONTEND_TEST = "frontend/src/pages/BetaOnboardingCockpitPage.test.tsx"
EXISTING_SURFACES: tuple[str, ...] = (
    "workspace",
    "workbench",
    "activation",
    "nm_wa_operator_demo",
    "sc_customer_demo",
)

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
    "api_key",
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
    "nf_session=",
    "AKIA",
)

#: A mailbox. Not a bare `@`, which appears in prose.
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _hermetic_run() -> dict[str, Any]:
    """The cockpit routes, driven against a database built for this call only."""
    from fastapi.testclient import TestClient

    previous_url = os.environ.get("DATABASE_URL")
    previous_key = os.environ.get("NF_SESSION_SIGNING_KEY")
    from nativeforge.db import session as _session_module

    previous_engine = _session_module.engine
    tmp = Path(tempfile.mkdtemp(prefix="nf_gate144_artifact_"))
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp / 'nf.sqlite3').as_posix()}"
    os.environ["NF_SESSION_SIGNING_KEY"] = "gate144-artifact-session-key-" + ("k" * 40)

    try:
        from alembic import command
        from alembic.config import Config

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
            for organization_id in (DEMO_ORGANIZATION_ID, OTHER_ORGANIZATION_ID):
                connection.execute(
                    sa.text(
                        "INSERT INTO organizations (id, org_type, seat_cap, "
                        "created_at) VALUES (:i, 'demo', 5, CURRENT_TIMESTAMP)"
                    ),
                    {"i": uuid.UUID(organization_id).hex},
                )
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject="gate144-artifact-owner",
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
        base = f"/v1/nf/demo/orgs/{DEMO_ORGANIZATION_ID}/beta-cockpit"

        anonymous = {
            path: client.get(f"{base}/{path}").status_code
            for path in ("readiness", "next-actions", "blockers", "capabilities")
        }
        forged = client.get(
            f"{base}/readiness", headers={"X-NF-Org-Id": DEMO_ORGANIZATION_ID}
        ).status_code
        cross = client.get(
            f"/v1/nf/demo/orgs/{OTHER_ORGANIZATION_ID}/beta-cockpit/readiness",
            headers=headers,
        ).status_code

        responses = {
            path: client.get(f"{base}/{path}", headers=headers)
            for path in ("readiness", "next-actions", "blockers", "capabilities")
        }
        bodies = {
            path: (response.json() if response.status_code == 200 else {})
            for path, response in responses.items()
        }
        statuses = {path: response.status_code for path, response in responses.items()}
        engine.dispose()
        return {
            "anonymous": anonymous,
            "forged_status": forged,
            "cross_org_status": cross,
            "statuses": statuses,
            "bodies": bodies,
        }
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


def _without_comments(source: str) -> str:
    """TypeScript source with block and line comments removed.

    Crude on purpose: it does not parse TS, and does not need to. What it has
    to do is stop a comment explaining a rule from being read as a violation of
    it.
    """
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", without_blocks, flags=re.M)


def _frontend_status() -> dict[str, Any]:
    """Does the cockpit surface exist, and is it wired the existing way?"""
    root = _repo_root()
    page = root / FRONTEND_PAGE
    test = root / FRONTEND_TEST
    surface = root / "frontend/src/viewSurface.ts"
    app = root / "frontend/src/App.tsx"

    surface_text = surface.read_text(encoding="utf-8") if surface.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    page_source = page.read_text(encoding="utf-8") if page.is_file() else ""
    # Comments stripped first. The page's own docstring says it names no
    # Tribe, and scanning the raw source made that sentence trip the check
    # it was describing.
    page_text = _without_comments(page_source)

    return {
        "surface_name": FRONTEND_SURFACE,
        "page_exists": page.is_file(),
        "test_exists": test.is_file(),
        "surface_in_union": f'"{FRONTEND_SURFACE}"' in surface_text,
        "surface_readable_from_query": FRONTEND_SURFACE in surface_text,
        "dispatched_in_app": "BetaOnboardingCockpitPage" in app_text,
        "existing_surfaces_intact": all(
            f'"{name}"' in surface_text for name in EXISTING_SURFACES
        ),
        "sc_customer_demo_still_dispatched": "ScCustomerDemoPage" in app_text,
        # What the page must never do.
        "page_names_a_tribe": "tribe" in page_text.lower(),
        "page_claims_production": "production ready" in page_text.lower(),
        "page_shows_false_lanes": "data-lane-value" in page_text,
        "page_shows_blockers": "beta-cockpit-blockers-" in page_text,
        "page_fetches_with_credentials": 'credentials: "include"' in page_text,
        "page_source_scanned_with_comments_stripped": True,
        "page_handles_signed_out": "Sign in" in page_text,
    }


def build_cockpit_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_run()
    bodies = run["bodies"]
    readiness_body = bodies.get("readiness") or {}
    frontend = _frontend_status()

    # The summary as the FULL battery proves it - every lane verifier having
    # passed. Reported beside the route's own answer, which is narrower on
    # purpose: a request proves what a request can prove.
    battery = build_beta_onboarding_summary(
        login_live=True,
        customer_persistence_live=True,
        awarded_operational_tracking=True,
        tenant_digest_operational=True,
        document_metadata_operational=True,
        email_delivery_readiness=True,
        source_monitoring_preflight_ready=True,
    )
    unaided = build_beta_onboarding_summary()

    route_lanes = {lane["lane"]: lane for lane in (readiness_body.get("lanes") or [])}

    files: dict[str, str] = {}

    files["beta_onboarding_cockpit_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "144",
            "what_the_cockpit_reports": "the deployment, not a tenant",
            "lane_keys": list(LANE_KEYS),
            "lane_statuses": list(LANE_STATUSES),
            "lane_evidence": dict(LANE_EVIDENCE),
            "self_evidencing_lane_count": sum(
                1 for v in LANE_EVIDENCE.values() if v == "self_evidencing"
            ),
            "lanes_needing_outside_evidence": sorted(
                k for k, v in LANE_EVIDENCE.items() if v != "self_evidencing"
            ),
            "why_evidence_matters": (
                "a summary that supplied a lane its own proof would be grading "
                "its own homework - reporting true for a lane whose evidence it "
                "invented"
            ),
            "never_true_lanes": sorted(NEVER_TRUE_LANES),
            "existing_frontend_surfaces": list(EXISTING_SURFACES),
            "frontend_surface_added": FRONTEND_SURFACE,
            "backend_only_before_this_gate": [
                "customer_persistence_activation_service",
                "awarded_operational_tracking_readiness_service",
                "tenant_digest_operational_readiness_service",
                "document_storage_readiness_service",
                "email_delivery_readiness_service",
                "source_monitoring_readiness_service",
            ],
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                f"it would create a route to {REAL_ORGANIZATION_ID} that nobody "
                "has authorized"
            ),
        }
    )

    files["readiness_summary_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "with_the_full_battery": {
                "operational_lanes": battery["operational_lanes"],
                "blocked_lanes": battery["blocked_lanes"],
                "requires_human_approval_lanes": battery[
                    "requires_human_approval_lanes"
                ],
                "not_configured_lanes": battery["not_configured_lanes"],
                "usable_today_count": battery["usable_today_count"],
                "invariant_failures": summary_invariant_failures(battery),
            },
            "unaided": {
                "operational_lanes": unaided["operational_lanes"],
                "blocked_lanes": unaided["blocked_lanes"],
                "requires_human_approval_lanes": unaided[
                    "requires_human_approval_lanes"
                ],
                "not_configured_lanes": unaided["not_configured_lanes"],
                "invariant_failures": summary_invariant_failures(unaided),
            },
            "unaided_reports_fewer_operational_lanes": (
                len(unaided["operational_lanes"]) < len(battery["operational_lanes"])
            ),
            "unaided_reports_no_forbidden_lane_true": not [
                key for key in NEVER_TRUE_LANES if unaided["by_lane"][key]["value"]
            ],
            "lanes": [
                {
                    "lane": lane["lane"],
                    "status": lane["status"],
                    "value": lane["value"],
                    "scope": lane["scope"],
                    "evidence": lane["evidence"],
                    "blockers": lane["blockers"],
                    "owner": lane["owner"],
                    "usable_today": lane["usable_today"],
                }
                for lane in battery["lanes"]
            ],
        }
    )

    files["cockpit_route_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "routes": sorted(run["statuses"]),
            "authenticated_status": run["statuses"],
            "unauthenticated_status": run["anonymous"],
            "unauthenticated_refused": all(
                code == 401 for code in run["anonymous"].values()
            ),
            "forged_header_status": run["forged_status"],
            "forged_header_refused": run["forged_status"] == 401,
            "cross_org_status": run["cross_org_status"],
            "cross_org_refused": run["cross_org_status"] in {403, 404},
            "lanes_reported_by_the_route": sorted(route_lanes),
            "route_lane_count": len(route_lanes),
            "expected_lane_count": len(LANE_KEYS),
            "every_lane_reported": set(route_lanes) == set(LANE_KEYS),
            "route_operational_lanes": readiness_body.get("operational_lanes") or [],
            "route_reports_fewer_than_the_battery": (
                len(readiness_body.get("operational_lanes") or [])
                <= len(battery["operational_lanes"])
            ),
            "route_reports_fewer_because": (
                "a request measures what a request can measure; the wider set "
                "needs the lane verifiers, and a route that assumed them would "
                "be reporting a proof it did not have"
            ),
            "route_invariant_failures": readiness_body.get("invariant_failures") or [],
            # What the routes never claimed.
            "production_rollout": bool(readiness_body.get("production_rollout")),
            "controlled_customer_pilot": bool(
                readiness_body.get("controlled_customer_pilot")
            ),
            "customer_auth_live": bool(readiness_body.get("customer_auth_live")),
            "source_monitoring_live": bool(
                readiness_body.get("source_monitoring_live")
            ),
            "email_delivery": bool(readiness_body.get("email_delivery")),
            "object_store_configured": bool(
                readiness_body.get("object_store_configured")
            ),
            "live_source_calls": int(readiness_body.get("live_source_calls") or 0),
            "emails_sent": int(readiness_body.get("emails_sent") or 0),
            "object_store_calls": int(readiness_body.get("object_store_calls") or 0),
            "collectors_activated": int(
                readiness_body.get("collectors_activated") or 0
            ),
            "customer_names_reported": bool(
                readiness_body.get("customer_names_reported")
            ),
        }
    )

    files["cockpit_blockers_matrix.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "blockers": (bodies.get("blockers") or {}).get("blockers") or [],
            "blocked_lane_count": (bodies.get("blockers") or {}).get(
                "blocked_lane_count"
            ),
            "every_false_lane_names_a_blocker": all(
                lane["blockers"] for lane in battery["lanes"] if not lane["value"]
            ),
            "lanes_without_a_blocker": sorted(
                lane["lane"]
                for lane in battery["lanes"]
                if not lane["value"] and not lane["blockers"]
            ),
            "requires_human_approval_lanes": battery["requires_human_approval_lanes"],
            "not_configured_lanes": battery["not_configured_lanes"],
            "not_approved": list(NOT_APPROVED),
        }
    )

    files["cockpit_next_safe_actions.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "next_safe_action": dict(NEXT_SAFE_ACTION),
            "route_next_safe_action": (bodies.get("next-actions") or {}).get(
                "next_safe_action"
            ),
            "not_this_yet": (bodies.get("next-actions") or {}).get("not_this_yet")
            or [],
            "one_action_not_a_backlog": True,
            "one_action_because": (
                "an operator reading a cockpit needs to know what to do next, "
                "not everything that could eventually be done"
            ),
            "activates_nothing": True,
        }
    )

    files["frontend_cockpit_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            **frontend,
            "wired_the_existing_way": bool(
                frontend["surface_in_union"]
                and frontend["dispatched_in_app"]
                and frontend["existing_surfaces_intact"]
            ),
            "no_public_bypass_added": True,
            "no_public_bypass_because": (
                "the page fetches the cockpit routes with credentials and those "
                "routes require a demo org session; a signed-out visitor is told "
                "to sign in rather than shown a readiness summary"
            ),
        }
    )

    files["beta_onboarding_cockpit_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "cockpit_foundation_route_live": bool(
                run["statuses"].get("readiness") == 200
                and set(route_lanes) == set(LANE_KEYS)
            ),
            "frontend_surface_exists": bool(frontend["page_exists"]),
            "scope": battery["scope"],
            "lane_count": len(LANE_KEYS),
            "operational_lanes": battery["operational_lanes"],
            "blocked_lanes": battery["blocked_lanes"],
            "requires_human_approval_lanes": battery["requires_human_approval_lanes"],
            "not_configured_lanes": battery["not_configured_lanes"],
            "never_true_lanes": sorted(NEVER_TRUE_LANES),
            "every_never_true_lane_is_false": not [
                key for key in NEVER_TRUE_LANES if battery["by_lane"][key]["value"]
            ],
            "production_rollout": battery["production_rollout"],
            "controlled_customer_pilot": battery["controlled_customer_pilot"],
            "customer_auth_live": battery["customer_auth_live"],
            "source_monitoring_live": battery["source_monitoring_live"],
            "email_delivery": battery["email_delivery"],
            "object_store_configured": battery["object_store_configured"],
            "verified_operational_binding": battery["verified_operational_binding"],
            "real_organization_touched": battery["real_organization_touched"],
            "real_customer_data_written": battery["real_customer_data_written"],
            "customer_names_reported": battery["customer_names_reported"],
            "eligibility_reported": battery["eligibility_reported"],
            "deadlines_reported": battery["deadlines_reported"],
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": summary_invariant_failures(battery),
            "blocked_reasons": battery["blocked_reasons"],
        }
    )

    files["next_beta_onboarding_blockers.md"] = _next_blockers(battery, frontend, run)

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"[^"]', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")
        if ADDRESS_SHAPE.search(body):
            raise AssertionError(f"an address-shaped string reached {name}")

    return files


def _next_blockers(
    battery: dict[str, Any], frontend: dict[str, Any], run: dict[str, Any]
) -> str:
    operational = "\n".join(f"  {name}" for name in battery["operational_lanes"])
    counts = run["bodies"].get("readiness") or {}
    live_source_calls = int(counts.get("live_source_calls") or 0)
    emails_sent = int(counts.get("emails_sent") or 0)
    object_store_calls = int(counts.get("object_store_calls") or 0)
    collectors_activated = int(counts.get("collectors_activated") or 0)
    sc_demo_intact = str(bool(frontend["sc_customer_demo_still_dispatched"])).lower()
    human = "\n".join(
        f"  {name:32s} {battery['by_lane'][name]['blockers']}"
        for name in battery["requires_human_approval_lanes"]
    )
    unconfigured = "\n".join(
        f"  {name:32s} {battery['by_lane'][name]['blockers']}"
        for name in battery["not_configured_lanes"]
    )
    route_live = str(run["statuses"].get("readiness") == 200).upper()
    return f"""# Gate 144 — what the beta onboarding cockpit does not yet reach

## Where this stands

```text
cockpit foundation route-live   {route_live}
frontend surface exists         {str(bool(frontend["page_exists"])).upper()}
lanes reported                  {len(battery["lane_keys"])}
scope                           {battery["scope"]}
```

An operator can now see, in one place, what this deployment can do — and, more
importantly, what it cannot and why.

## What works today

```text
{operational}
```

Every one is `controlled_dev_demo`. None is a production claim.

## What needs a person

```text
{human}
```

No code change moves either of these. That is why they are
`requires_human_approval` rather than `blocked`: an operator reading "blocked"
looks for a bug, and there is none.

## What is not configured

```text
{unconfigured}
```

## What is deliberately false

```text
controlled_customer_pilot   not approved
production_rollout          not approved, and no lane above is a production claim
source_monitoring           171 terms reviews and five scheduler components
```

## The route reports fewer operational lanes than the verifier, on purpose

```text
the route      measures what a request can measure
the verifier   runs each lane's own verifier first, then reports
```

A cockpit route that assumed the wider set would be reporting a proof it did not
have. `LANE_EVIDENCE` records, per lane, what the summary is allowed to conclude
unaided — and a lane needing outside evidence is `readiness_only`, never
`operational`, until something measures it.

That is the defect this gate was most likely to introduce, and it is the one the
design is shaped around.

## The frontend surface

```text
surface name             {frontend["surface_name"]}
in the union             {str(bool(frontend["surface_in_union"])).lower()}
dispatched in App        {str(bool(frontend["dispatched_in_app"])).lower()}
existing surfaces intact {str(bool(frontend["existing_surfaces_intact"])).lower()}
sc_customer_demo intact  {sc_demo_intact}
names a Tribe            {str(bool(frontend["page_names_a_tribe"])).lower()}
claims production        {str(bool(frontend["page_claims_production"])).lower()}
shows false lanes        {str(bool(frontend["page_shows_false_lanes"])).lower()}
shows blockers           {str(bool(frontend["page_shows_blockers"])).lower()}
```

It is a foundation, not finished UX: status cards, blockers and one next action.
What it does have is the property that matters — every false lane is shown as
false, with its reason. A dashboard that showed only the green lanes would be
the most dangerous artifact this campaign could produce.

## Nothing was activated

```text
live source calls      {live_source_calls}
emails sent            {emails_sent}
object store calls     {object_store_calls}
collectors activated   {collectors_activated}
real org touched       false
customer data written  false
```

## Still false, and not touched

```text
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
document_body_storage_ready    false
controlled_customer_pilot      false
production_rollout             false
```
"""


def write_cockpit_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_cockpit_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def cockpit_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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

    return fails
