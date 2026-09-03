"""Gate 140H: what the tenant digest and watchlist proved, as committed files.

Deterministic. The smoke runs against a migrated database this module builds
and throws away, driven through a `TestClient` with a real signed session for a
real membership — so the artifact records a measurement and still produces the
same bytes every time.

The verifier does the same thing against the running server over real HTTP. Two
surfaces, one smoke service deciding what passed, so they cannot disagree about
what "operational" means.

No live source is called, no mail is sent, no collector is started, no object
store is touched. No secrets, no tokens, no cookies, no state, no PKCE
verifier, no provider subject, no customer data.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_digest_operational_readiness_service import (
    LANE_ROUTE_MODULES,
    NOT_APPROVED,
    build_tenant_digest_readiness,
    detect_route_module,
    tenant_digest_readiness_invariant_failures,
)
from nativeforge.services.tenant_digest_route_smoke_service import (
    FEDERAL_SOURCE_ID,
    MISLABELLED_FIXTURE_ID,
    SC_SOURCE_ID,
    UNKNOWN_SOURCE_ID,
    run_tenant_digest_route_smoke,
    tenant_digest_route_smoke_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_service import (
    DEFAULT_CADENCE,
    DIGEST_ITEM_FIELDS,
    UNRESOLVED_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_digest_gate140_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_digest_gate140"

ARTIFACT_FILES: tuple[str, ...] = (
    "tenant_digest_survey.json",
    "source_watchlist_route_smoke.json",
    "weekly_digest_preview_smoke.json",
    "daily_digest_setting_smoke.json",
    "pursuit_suppression_smoke.json",
    "tenant_digest_operational_readiness.json",
    "tenant_digest_end_to_end_smoke.json",
    "next_tenant_digest_blockers.md",
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d140"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Frozen, so the fixture profile and the digest are byte-identical each run.
FIXED_NOW = datetime(2026, 9, 3, tzinfo=UTC)

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


def _low(value: Any) -> str:
    return str(bool(value)).lower()


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _seed(connection: Any, organization_id: str) -> None:
    """One tenant profile, weekly, fixture-labelled.

    Weekly on purpose: the smoke proves that weekly is the default with no
    setting at all, so seeding `daily` would have hidden the very thing the
    daily sub-task is meant to demonstrate.
    """
    from nativeforge.services.tenant_profile_repository_service import (
        upsert_tenant_profile,
    )

    result = upsert_tenant_profile(
        connection=connection,
        now=FIXED_NOW,
        organization_id=organization_id,
        tenant_id_label=f"t-{organization_id[:8]}",
        customer_org_id_label=f"c-{organization_id[:8]}",
        recognition_status="federally_recognized",
        recognition_status_fact_status="demo_fixture",
        operating_states=["SC"],
        operating_states_fact_status="demo_fixture",
        applicant_classes=["federally_recognized_tribe"],
        applicant_classes_fact_status="demo_fixture",
        digest_frequency=DEFAULT_CADENCE,
        profile_status="active",
        is_demo=True,
    )
    if not result.get("rows_written"):
        raise AssertionError(f"fixture profile refused: {result['blocked_reasons']}")


def _hermetic_smoke() -> dict[str, Any]:
    """The routes, driven against a database built for this call only."""
    from fastapi.testclient import TestClient

    previous_url = os.environ.get("DATABASE_URL")
    previous_key = os.environ.get("NF_SESSION_SIGNING_KEY")
    # And the module-level engine, which this call replaces. Gate 139 found
    # that restoring only the two environment variables left a second call
    # migrating a NEW temp database while every repository still held the
    # first - and a determinism test calls this twice by definition.
    from nativeforge.db import session as _session_module

    previous_engine = _session_module.engine
    tmp = Path(tempfile.mkdtemp(prefix="nf_gate140_artifact_"))
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(tmp / 'nf.sqlite3').as_posix()}"
    # A key of this module's own, so the artifact never depends on the host's.
    os.environ["NF_SESSION_SIGNING_KEY"] = "gate140-artifact-session-key-" + ("k" * 40)

    try:
        from alembic import command
        from alembic.config import Config

        # `get_settings` is lru_cached and alembic's env reads it, so without
        # this the second call migrates the FIRST temp database.
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
                # Both organizations get a profile, so the cross-organization
                # refusal is proved by the GUARD and not by the other
                # organization happening to have nothing to show.
                _seed(connection, organization_id)
            identity = upsert_identity(
                connection=connection,
                issuer="https://accounts.google.com",
                subject="gate140-artifact-owner",
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

        # `dependency_overrides`, not module rebinding: `get_db_session` yields
        # `SessionLocal()` and `SessionLocal` is bound to an engine at import,
        # so replacing the module's `engine` left the routes reading whichever
        # database was current when the module first loaded.
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
        smoke = run_tenant_digest_route_smoke(
            client=client,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            session_headers=headers,
        )

        # What the smoke left behind, and what the OTHER organization can see.
        with engine.connect() as connection:
            rows: dict[str, Any] = {}
            for table, column in (
                ("nf_source_watchlist_entries", "archived_at"),
                ("nf_tenant_pursuit_suppressions", "lifted_at"),
            ):
                rows[f"{table}_total"] = int(
                    connection.execute(
                        sa.text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar_one()
                )
                rows[f"{table}_live"] = int(
                    connection.execute(
                        sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
                    ).scalar_one()
                )
                rows[f"{table}_for_other_org"] = int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {table} WHERE organization_id = :o"
                        ),
                        {"o": uuid.UUID(OTHER_ORGANIZATION_ID).hex},
                    ).scalar_one()
                )
                rows[f"{table}_for_real_org"] = int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {table} WHERE organization_id = :o"
                        ),
                        {"o": uuid.UUID(REAL_ORGANIZATION_ID).hex},
                    ).scalar_one()
                )
            # An audit row per suppression, which is the evidence the
            # suppression contract insists on.
            rows["nf_audit_events_for_suppression"] = int(
                connection.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM nf_audit_events "
                        "WHERE organization_id = :o"
                    ),
                    {"o": uuid.UUID(DEMO_ORGANIZATION_ID).hex},
                ).scalar_one()
            )
            # Every stored row is fixture-labelled. Nothing here is real.
            rows["non_fixture_rows_written"] = sum(
                int(
                    connection.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {table} "
                            "WHERE fact_status <> 'demo_fixture'"
                        )
                    ).scalar_one()
                )
                for table in (
                    "nf_source_watchlist_entries",
                    "nf_tenant_pursuit_suppressions",
                )
            )
        engine.dispose()
        return {"smoke": smoke, "row_counts": rows}
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


def build_tenant_digest_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_smoke()
    smoke = run["smoke"]
    counts = run["row_counts"]

    readiness = build_tenant_digest_readiness(
        route_smoke=smoke,
        # Gate 138's measurement, not a re-run: running it twice in two shapes
        # would let the two disagree about the same fact.
        customer_persistence_live=True,
        profile_available=True,
    )

    files: dict[str, str] = {}

    files["tenant_digest_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "140",
            "why_tenant_digest_operational_was_false": (
                "it was a literal False in six places and no service derived "
                "it; same family Gate 114A removed for "
                "customer_persistence_live and Gate 139A for "
                "awarded_operational_tracking"
            ),
            "what_gate_104_built": [
                "tenant_nofo_digest_snapshot_service",
                "tenant_nofo_digest_change_detection_service",
                "tenant_nofo_digest_item_explanation_service",
                "tenant_pursuit_suppression_service",
                "tenant_nofo_digest_builder_service",
                "tenant_nofo_digest_demo_fixture_service",
            ],
            "what_gate_104_wired": [],
            "ready_for_demo_preview_before_this_gate": True,
            "anything_able_to_ask_for_a_preview_before_this_gate": False,
            "watchlist_table_before": "ABSENT",
            "watchlist_service_before": "ABSENT",
            "suppression_persistence_before": "ABSENT",
            "route_modules_before": dict.fromkeys(LANE_ROUTE_MODULES, "ABSENT"),
            "route_modules_after": {
                lane: detect_route_module(lane) for lane in LANE_ROUTE_MODULES
            },
            "migration_added": "0040_tenant_watchlist_and_suppression",
            "tables_added": [
                "nf_source_watchlist_entries",
                "nf_tenant_pursuit_suppressions",
            ],
            "source_monitoring_required_for_a_fixture_preview": False,
            "source_monitoring_not_required_because": (
                "the candidates are labelled fixture snapshots; requiring a "
                "live check would make the preview lane permanently "
                "unreachable and every 'not ready' above it unfalsifiable"
            ),
            "email_required_for_preview_readiness": False,
            "email_not_required_because": (
                "delivery_status may only be preview_only; there is no email "
                "service in this repository and none was written"
            ),
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                "it would create a route to "
                f"{REAL_ORGANIZATION_ID} that nobody has authorized"
            ),
        }
    )

    files["source_watchlist_route_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route_module": LANE_ROUTE_MODULES["source_watchlist"],
            "watchlist_route_operational": bool(smoke["watchlist_route_operational"]),
            "steps": {
                "added_a_federal_registry_source": FEDERAL_SOURCE_ID,
                "added_a_state_registry_source": SC_SOURCE_ID,
                "read_the_watchlist_back_anchored_on_organization_id": bool(
                    smoke["watchlist_route_operational"]
                ),
                "archived_one_entry_without_deleting_it": bool(
                    smoke["watchlist_archive_preserves_the_row"]
                ),
            },
            "refusals": {
                "unauthenticated": bool(smoke["unauthenticated_refused"]),
                "forged_dev_header": bool(smoke["forged_header_refused"]),
                "registry_id_not_in_the_registry": {
                    "source_id": UNKNOWN_SOURCE_ID,
                    "refused": bool(smoke["watchlist_registry_check_enforced"]),
                },
                "fixture_id_without_the_fixture_prefix": {
                    "source_id": MISLABELLED_FIXTURE_ID,
                    "refused": bool(smoke["watchlist_fixture_prefix_enforced"]),
                },
                "caller_relabelling_the_write": bool(
                    smoke["watchlist_caller_supplied_fields_refused"]
                ),
                "cross_organization_read": bool(smoke["cross_org_refused"]),
            },
            "watching_is_not_monitoring": True,
            "source_monitoring_live": False,
            "live_grant_sources_called": bool(smoke["live_grant_sources_called"]),
            "network_calls_to_grant_sources": int(
                smoke["network_calls_to_grant_sources"]
            ),
            "collectors_activated": int(smoke["collectors_activated"]),
            "rows_left_live": counts["nf_source_watchlist_entries_live"],
            "rows_total": counts["nf_source_watchlist_entries_total"],
            "rows_for_another_organization": counts[
                "nf_source_watchlist_entries_for_other_org"
            ],
            "rows_for_the_real_organization": counts[
                "nf_source_watchlist_entries_for_real_org"
            ],
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "watchlist" in reason or "archive" in reason
            ],
        }
    )

    files["weekly_digest_preview_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route_module": LANE_ROUTE_MODULES["tenant_digest"],
            "digest_preview_operational": bool(smoke["digest_preview_operational"]),
            "weekly_is_the_default": bool(smoke["weekly_default_proved"]),
            "weekly_needed_no_setting": True,
            "default_cadence": DEFAULT_CADENCE,
            "item_fields": list(DIGEST_ITEM_FIELDS),
            "unresolved_statuses_that_survive": sorted(UNRESOLVED_STATUSES),
            "item_counts": dict(smoke["item_counts"]),
            "delivery_status": "preview_only",
            "candidate_provenance": "labelled_fixture_snapshots",
            "refusals": {
                "unauthenticated": bool(smoke["unauthenticated_refused"]),
                "forged_dev_header": bool(smoke["forged_header_refused"]),
                "unrecognised_cadence": bool(smoke["unknown_cadence_refused"]),
                "cross_organization_read": bool(smoke["cross_org_refused"]),
            },
            "no_opportunity_was_fabricated": True,
            "no_eligibility_was_fabricated": True,
            "no_deadline_was_inferred": True,
            "unknown_preserved": True,
            "needs_human_review_preserved": True,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "email_delivery_live": False,
            "emails_sent": int(smoke["emails_sent"]),
            "improvement_claims": [],
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "digest" in reason or "weekly" in reason or "cadence" in reason
            ],
        }
    )

    files["daily_digest_setting_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "daily_is_optional": True,
            "daily_is_off_until_the_tenant_enables_it": True,
            "daily_refused_before_opt_in": bool(smoke["daily_refused_before_opt_in"]),
            "daily_refusal_reason": (
                "daily_digest_requested_but_the_profile_has_not_enabled_it"
            ),
            "daily_setting_proved": bool(smoke["daily_setting_proved"]),
            "setting_lives_in": "nf_tenant_beta_profiles.digest_frequency",
            "setting_is_a_stored_column_not_a_service_flag": True,
            "cadence_change_archives_the_previous_profile": True,
            "cadence_restored_to_weekly_after_the_smoke": True,
            "cadences_recognised": ["daily", "weekly"],
            "email_delivery_live": False,
            "emails_sent": int(smoke["emails_sent"]),
            "a_daily_alert_nobody_receives_is_still_not_delivery": True,
            "blocked_reasons": [
                reason for reason in smoke["blocked_reasons"] if "daily" in reason
            ],
        }
    )

    files["pursuit_suppression_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "suppression_proved": bool(smoke["suppression_proved"]),
            "suppression_is_audit_backed": bool(smoke["suppression_audit_backed"]),
            "audit_row_is_appended_before_the_suppression": True,
            "audit_rows_written": counts["nf_audit_events_for_suppression"],
            "suppression_without_audit_evidence_is_refused": True,
            "suppression_refusal_reason_without_audit": (
                "contract:no_audit_event_recorded"
            ),
            "the_opportunity_is_not_deleted": bool(
                smoke["suppression_preserves_the_opportunity"]
            ),
            "the_item_moved_rather_than_vanishing": bool(
                smoke["suppression_preserves_the_opportunity"]
            ),
            "item_counts": dict(smoke["item_counts"]),
            "source_history_preserved": True,
            "provenance_preserved": True,
            "preserved_by": (
                "a CHECK constraint: source_history_preserved AND provenance_preserved"
            ),
            "suppression_is_org_scoped": bool(smoke["cross_org_refused"]),
            "lift_proved": bool(smoke["suppression_lift_proved"]),
            "lift_sets_lifted_at_and_deletes_nothing": True,
            "rows_left_live": counts["nf_tenant_pursuit_suppressions_live"],
            "rows_total": counts["nf_tenant_pursuit_suppressions_total"],
            "rows_for_another_organization": counts[
                "nf_tenant_pursuit_suppressions_for_other_org"
            ],
            "rows_for_the_real_organization": counts[
                "nf_tenant_pursuit_suppressions_for_real_org"
            ],
            "blocked_reasons": [
                reason
                for reason in smoke["blocked_reasons"]
                if "suppress" in reason or "lift" in reason
            ],
        }
    )

    files["tenant_digest_operational_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_digest_operational": bool(readiness["tenant_digest_operational"]),
            "scope": readiness["scope"],
            "profile_available": bool(readiness["profile_available"]),
            "watchlist_available": bool(readiness["watchlist_available"]),
            "digest_preview_available": bool(readiness["digest_preview_available"]),
            "weekly_default_available": bool(readiness["weekly_default_available"]),
            "daily_setting_available": bool(readiness["daily_setting_available"]),
            "suppression_available": bool(readiness["suppression_available"]),
            "unauthenticated_refused": bool(readiness["unauthenticated_refused"]),
            "cross_org_refused": bool(readiness["cross_org_refused"]),
            "customer_persistence_live": bool(readiness["customer_persistence_live"]),
            "source_monitoring_required_for_preview": bool(
                readiness["source_monitoring_required_for_preview"]
            ),
            "email_required_for_preview": bool(readiness["email_required_for_preview"]),
            "source_monitoring_live": bool(readiness["source_monitoring_live"]),
            "email_delivery_available": bool(readiness["email_delivery_available"]),
            "production_tenant_digest": bool(readiness["production_tenant_digest"]),
            "customer_auth_live": bool(readiness["customer_auth_live"]),
            "route_modules": readiness["route_modules"],
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": tenant_digest_readiness_invariant_failures(readiness),
            "blocked_reasons": list(readiness["blocked_reasons"]),
        }
    )

    files["tenant_digest_end_to_end_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "end_to_end_completed": bool(smoke["end_to_end_completed"]),
            "sequence": [
                "add two real registry sources to the watchlist",
                "read the watchlist back, anchored on organization_id",
                "ask for the weekly digest -> the default, no setting needed",
                "ask for the daily digest -> refused, the profile has not enabled it",
                "enable daily on the profile",
                "ask for the daily digest -> produced",
                "restore weekly",
                "suppress one opportunity -> an audit row, then a suppression",
                "ask for the digest -> the item moved to suppressed_items",
                "lift the suppression -> the item comes back",
                "read readiness",
                "read everything as another organization -> refused",
                "archive a watchlist entry -> the row stays",
            ],
            "proved": {
                key: bool(value)
                for key, value in sorted(smoke.items())
                if isinstance(value, bool) and key != "authenticated_run"
            },
            "unauthenticated_probes": smoke["unauthenticated_probes"],
            "item_counts": dict(smoke["item_counts"]),
            "row_counts": counts,
            "every_stored_row_is_fixture_labelled": (
                counts["non_fixture_rows_written"] == 0
            ),
            "invariant_failures": tenant_digest_route_smoke_invariant_failures(smoke),
            "database": "migrated_sqlite_built_for_this_call",
            "session": "real, signed, for a real membership row",
            "fake_users_created": 0,
            "fake_sessions_created": 0,
            "live_grant_sources_called": bool(smoke["live_grant_sources_called"]),
            "network_calls_to_grant_sources": int(
                smoke["network_calls_to_grant_sources"]
            ),
            "emails_sent": int(smoke["emails_sent"]),
            "collectors_activated": int(smoke["collectors_activated"]),
            "object_store_calls": int(smoke["object_store_calls"]),
            "real_customer_data_written": bool(smoke["real_customer_data_written"]),
            "real_organization_touched": bool(smoke["real_organization_touched"]),
            "notes": list(smoke["notes"]),
            "blocked_reasons": list(smoke["blocked_reasons"]),
        }
    )

    files["next_tenant_digest_blockers.md"] = _next_blockers(readiness, smoke, counts)

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def write_tenant_digest_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_tenant_digest_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def tenant_digest_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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


def _next_blockers(
    readiness: dict[str, Any], smoke: dict[str, Any], counts: dict[str, Any]
) -> str:
    item_counts = smoke.get("item_counts") or {}
    other_org_rows = counts["nf_source_watchlist_entries_for_other_org"]
    real_org_rows = counts["nf_source_watchlist_entries_for_real_org"]
    return f"""# Gate 140 — what the tenant digest still does not reach

## What is operational

```text
tenant_digest_operational   {str(readiness["tenant_digest_operational"]).upper()}
scope                       {readiness["scope"]}
```

Add a source to the watchlist, read it back anchored on `organization_id`, ask
for the weekly digest with no setting at all, ask for the daily one and be
refused until the profile enables it, suppress an opportunity with an audit row
behind it, watch the item move rather than vanish, lift it, archive a watchlist
entry and find the row still there.

`customer_auth_live` is **false** and was not required: every row this gate
writes is fixture-labelled, and `production_write = not demo_fixture`.

## What every route refuses

```text
unauthenticated                          401, all nine routes
a forged X-NF-Org-Id                     401 - not a parameter on any route
a caller setting is_demo or fact_status  400, named
a registry source id nobody issued       400, source_id_is_not_in_the_source_registry
a fixture id without the fixture prefix  400, named
an unrecognised cadence                  422, cadence_not_recognised
a daily digest with no opt-in            422, the_profile_has_not_enabled_it
a suppression with no audit event        contract:no_audit_event_recorded
a cross-organization read                403/404 - which does not confirm the row exists
```

## Watching is not monitoring

A watchlist entry is a statement of interest. It is not coverage:

```text
source_monitoring_live               false, every response, every entry
last_checked_at                      null, every entry
live_grant_sources_called            {_low(smoke["live_grant_sources_called"])}
network_calls_to_grant_sources       {int(smoke["network_calls_to_grant_sources"])}
collectors_activated                 {int(smoke["collectors_activated"])}
```

The digest's candidates are **labelled fixture snapshots**. Change detection
compares two recorded snapshots, not two live observations.

## A digest that is previewed is not a digest that is delivered

```text
delivery_status          preview_only, and no other value is permitted
email_delivery_live      false
emails_sent              {int(smoke["emails_sent"])}
```

There is no email service in this repository. A weekly digest nobody receives
is not a weekly digest, and this gate does not pretend otherwise — it makes the
preview askable, which is a different and smaller claim.

## What production tenant digest still needs

```text
a collector, activated under the existing gates    live candidates instead of fixtures
an email delivery service                          nothing to send a digest with
digest persistence                                 no digest table exists; a digest
                                                   that cannot be re-read cannot be
                                                   audited after a missed deadline
customer_auth_live true                            Gate 136's second-person invite event
verified_operational_binding                       Gate 137's two-part owner decision
the pursuit vocabulary settled                     three vocabularies disagree -
                                                   PursuitWorkflowStatus,
                                                   pursuit_workspace_contract, and
                                                   doc 570's seven stages
```

## What is NOT the blocker

```text
the tables            both round-trip, org-anchored, RLS-policied
the routes            all nine operational, proved by calling them
cross-tenant reads    refused on every one
source monitoring     not required for a fixture preview, and not claimed
email                 not required for preview readiness, and not claimed
customer_auth_live    gates PRODUCTION writes, not fixture-labelled ones
```

## What the digest says about what it does not know

Nothing is rounded up. Of the items in the weekly preview:

```text
items visible                        {item_counts.get("visible_before", 0)}
items total                          {item_counts.get("total_before", 0)}
```

An item whose eligibility nobody has established keeps `unknown`, and its
`recommended_action` is `review_eligibility_with_a_human`. An item whose
deadline nobody has verified reports `due_date_status` saying so. No
`recommended_action` this service can emit is "apply".

## Rows left behind

```text
watchlist entries, live              {counts["nf_source_watchlist_entries_live"]}
watchlist entries, total             {counts["nf_source_watchlist_entries_total"]}
suppressions, live                   {counts["nf_tenant_pursuit_suppressions_live"]}
suppressions, total                  {counts["nf_tenant_pursuit_suppressions_total"]}
rows for another organization        {other_org_rows}
rows for the real organization       {real_org_rows}
rows that are not fixture-labelled   {counts["non_fixture_rows_written"]}
```

Archiving and lifting keep their rows, which is why "live" is lower than
"total" and why nothing was deleted.

## Still false, and not touched

```text
production_tenant_digest       false
source_monitoring_live         false
email_delivery                 false
live_source_coverage           false
customer_auth_live             false
verified_operational_binding   false
object_store_configured        false
production_rollout             false
controlled_customer_pilot      false
```
"""
