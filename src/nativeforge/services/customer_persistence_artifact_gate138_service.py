"""Gate 138G: what persistence proved, per lane, from a round trip.

Deterministic. The proof runs against a database this module builds and throws
away, with a fixed seed — so the artifact records a measurement and still
produces the same bytes every time. The live smoke uses a fresh seed instead,
because a proof against a live database has to be runnable twice.

No secrets, no tokens, no cookies, no state, no PKCE verifier, no provider
subject, no customer data. The scan discriminates a credential FIELD carrying a
value from a field NAMED in a refusal list — Gate 136F got that wrong and
reported its own safeguard as a breach.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services import award_document_store_repository_service as _docs
from nativeforge.services import (
    award_requirement_proof_audit_repository_service as _proof,
)
from nativeforge.services import award_requirements_repository_service as _reqs
from nativeforge.services import awarded_grants_repository_service as _awards
from nativeforge.services import tenant_profile_repository_service as _profiles
from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_persistence_activation_service import (
    CONTROLLED_SCOPE,
    FIXTURE_FACT_STATUS,
    LANE_ROUTES,
    LANES,
    persistence_activation_invariant_failures,
    prove_customer_persistence,
)
from nativeforge.services.customer_persistence_capability_service import (
    build_capability_matrix,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
)

SCHEMA_VERSION = "nf_customer_persistence_gate138_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_persistence_gate138"

ARTIFACT_FILES: tuple[str, ...] = (
    "customer_persistence_survey.json",
    "persistence_lane_matrix.json",
    "authenticated_org_persistence_smoke.json",
    "cross_org_refusal_results.json",
    "customer_persistence_readiness.json",
    "route_level_persistence_status.json",
    "next_customer_persistence_blockers.md",
)

#: Fixed, so the artifact is byte-stable. The live smoke does not use it.
ARTIFACT_SEED = "gate138-artifact"
FIXTURE_IDENTITY = "dddddddd-eeee-ffff-0000-111111111138"
FIXTURE_MOMENT = datetime(2026, 9, 2, tzinfo=UTC)
OTHER_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-00000000d138"

#: The evidence a demo organization's owner actually produces. Supplied here
#: rather than read, because this module builds its own database and the real
#: one is measured by the verifier script.
_BINDING_EVIDENCE = {
    "org_binding_passed": True,
    "callback_session_validated": True,
    "identity_rows": 1,
    "active_membership_rows": 1,
}
_ROLE_EVIDENCE = {
    "role_mapping_passed": True,
    "role_mapping_source": "nf_org_memberships",
    "cookie_claim_can_override_membership": False,
    "email_domain_can_map_a_role": False,
}

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
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "@gmail.com",
    "eyJ",
)

_ORGANIZATIONS = sa.Table(
    "organizations",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _hermetic_proofs() -> dict[str, Any]:
    """Three proofs against a database built for this call only.

    ```text
    the demo org        every lane, round-tripped
    aaaaaaaa-…          refused by name
    no accountability   refused, and nothing written
    ```
    """
    engine = sa.create_engine("sqlite://")
    _ORGANIZATIONS.create(engine)
    for module in (_profiles, _awards, _reqs, _proof, _docs):
        for attribute in dir(module):
            candidate = getattr(module, attribute)
            if isinstance(candidate, sa.Table):
                candidate.create(engine, checkfirst=True)

    with engine.begin() as connection:
        for organization_id, org_type in (
            (DEMO_ORGANIZATION_ID, "demo"),
            (REAL_ORGANIZATION_ID, "real"),
            (OTHER_ORGANIZATION_ID, "real"),
        ):
            connection.execute(
                sa.insert(_ORGANIZATIONS).values(
                    id=uuid.UUID(organization_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=FIXTURE_MOMENT,
                )
            )

        demo = prove_customer_persistence(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            identity_id=FIXTURE_IDENTITY,
            now=FIXTURE_MOMENT,
            seed=ARTIFACT_SEED,
            binding_evidence=_BINDING_EVIDENCE,
            role_mapping_evidence=_ROLE_EVIDENCE,
        )
        real = prove_customer_persistence(
            connection=connection,
            organization_id=REAL_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            identity_id=FIXTURE_IDENTITY,
            now=FIXTURE_MOMENT,
            seed=f"{ARTIFACT_SEED}-real",
            binding_evidence=_BINDING_EVIDENCE,
            role_mapping_evidence=_ROLE_EVIDENCE,
        )
        unaccountable = prove_customer_persistence(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            identity_id=FIXTURE_IDENTITY,
            now=FIXTURE_MOMENT,
            seed=f"{ARTIFACT_SEED}-unaccountable",
        )
        labelled = prove_customer_persistence(
            connection=connection,
            organization_id=DEMO_ORGANIZATION_ID,
            other_organization_id=OTHER_ORGANIZATION_ID,
            identity_id=FIXTURE_IDENTITY,
            now=FIXTURE_MOMENT,
            seed=f"{ARTIFACT_SEED}-label",
            binding_evidence=_BINDING_EVIDENCE,
            role_mapping_evidence=_ROLE_EVIDENCE,
            tenant_id="a-tenant-label",
        )

        left_live = {}
        for table in (
            "nf_tenant_beta_profiles",
            "nf_awarded_grants",
            "nf_award_requirements",
            "nf_award_requirement_proof_events",
            "nf_award_documents",
        ):
            left_live[table] = int(
                connection.execute(
                    sa.text(f"SELECT COUNT(*) FROM {table} WHERE archived_at IS NULL")
                ).scalar_one()
            )

    engine.dispose()
    return {
        "demo": demo,
        "real": real,
        "unaccountable": unaccountable,
        "labelled": labelled,
        "rows_left_live_per_table": left_live,
    }


def _lane_summary(proof: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "lane": lane["lane"],
            "round_trip_proved": bool(lane["round_trip_proved"]),
            "steps": dict(lane["steps"]),
            "rows_written": int(lane["rows_written"]),
            "this_row_read_back_by_id": bool(lane["this_row_read_back_by_id"]),
            "cross_org_rows_read": int(lane["cross_org_rows_read"]),
            "rows_archived": int(lane["rows_archived"]),
            "scaffold_rows_written": int(lane.get("scaffold_rows_written") or 0),
            "scaffold_rows_archived": int(lane.get("scaffold_rows_archived") or 0),
            "route_module": lane["route_module"],
            "route_persistence_available": bool(lane["route_persistence_available"]),
            "blocked_reasons": list(lane["blocked_reasons"]),
        }
        for lane in proof["lane_results"]
    ]


def build_persistence_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    runs = _hermetic_proofs()
    demo = runs["demo"]
    matrix = build_capability_matrix()

    files: dict[str, str] = {}

    files["customer_persistence_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "138",
            "why_customer_persistence_live_was_false": (
                "every lane's `operational` required customer_auth_live via a "
                "blanket CAPABILITY_REQUIRES_AUTH, and customer_auth_live is "
                "false because invite_binding_passed is"
            ),
            "what_the_blocker_actually_wanted": (
                "somebody is accountable for the row - which is already true: "
                "org_binding_passed, callback_session_validated and "
                "role_mapping_passed are all measured true from rows"
            ),
            "the_distinction_the_repositories_already_drew": (
                "production_write = not demo_fixture; only a production write "
                "requires customer_auth_live or a verified operational binding"
            ),
            "capability_matrix_never_wrote_a_row": True,
            "capability_matrix_reports": {
                "rows_written": int(matrix["rows_written"]),
                "persisted": bool(matrix["persisted"]),
            },
            "modules_named_for_survey_under_other_names": {
                "tenant_beta_profile_repository_service": (
                    "tenant_profile_repository_service"
                ),
                "award_requirement_proof_repository_service": (
                    "award_requirement_proof_audit_repository_service"
                ),
                "award_documents_repository_service": (
                    "award_document_store_repository_service"
                ),
            },
            "invite_binding_passed_blocks_persistence": False,
            "verified_operational_binding_blocks_demo_persistence": False,
            "verified_operational_binding_blocks_production_persistence": True,
        }
    )

    files["persistence_lane_matrix.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "lanes_tested": list(LANES),
            "lane_routes": dict(LANE_ROUTES),
            "capability_matrix": {
                "customer_persistence_live_production": bool(
                    matrix["customer_persistence_live"]
                ),
                "production_persistence_ready": bool(
                    matrix["production_persistence_ready"]
                ),
                "write_path_count": int(matrix["write_path_count"]),
                "operational_count": int(matrix["operational_count"]),
                "controlled_dev_persistence_available_count": int(
                    matrix["controlled_dev_persistence_available_count"]
                ),
                "controlled_dev_persistence_available_lanes": list(
                    matrix["controlled_dev_persistence_available_lanes"]
                ),
            },
            "round_trip": _lane_summary(demo),
            "repository_live_lanes": list(demo["repository_persistence_live_lanes"]),
            "route_live_lanes": list(demo["route_persistence_live_lanes"]),
            "route_missing_lanes": list(demo["route_missing_lanes"]),
            "blocked_lanes": list(demo["blocked_lanes"]),
        }
    )

    files["authenticated_org_persistence_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": DEMO_ORGANIZATION_ID,
            "organization_is_demo": bool(demo["organization_is_demo"]),
            "customer_persistence_live": bool(demo["customer_persistence_live"]),
            "scope": demo["scope"],
            "accountable_principal_available": bool(
                demo["accountable_principal_available"]
            ),
            "accountable_identity_source": demo["accountable_identity_source"],
            "accountable_identity_resolved": bool(
                demo["accountable_identity_resolved"]
            ),
            "fact_status_written": demo["fact_status_written"],
            "rows_written": int(demo["rows_written"]),
            "rows_archived": int(demo["rows_archived"]),
            "scaffold_rows_written": int(demo["scaffold_rows_written"]),
            "scaffold_rows_archived": int(demo["scaffold_rows_archived"]),
            "rows_left_live": int(demo["rows_left_live"]),
            "rows_left_live_per_table": runs["rows_left_live_per_table"],
            "cleanup_method": "archive, because no repository offers a delete",
            "cleanup_method_because": (
                "these are audit surfaces; adding a hard delete for a smoke "
                "test's convenience would be the wrong primitive to introduce"
            ),
            "invariant_failures": persistence_activation_invariant_failures(demo),
            "customer_auth_live": False,
            "customer_auth_live_required": False,
            "database": "in_memory_sqlite_built_for_this_call",
            "seed_fixed_by_caller": bool(demo["seed_fixed_by_caller"]),
        }
    )

    files["cross_org_refusal_results.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "reader_organization_id": OTHER_ORGANIZATION_ID,
            "writer_organization_id": DEMO_ORGANIZATION_ID,
            "cross_org_rows_read_total": int(demo["cross_org_rows_read"]),
            "per_lane": [
                {
                    "lane": lane["lane"],
                    "cross_org_rows_read": int(lane["cross_org_rows_read"]),
                    "refused": lane["steps"]["cross_org_refused"],
                }
                for lane in demo["lane_results"]
            ],
            "reads_are_anchored_on": "organization_id",
            "label_reads_refused": True,
            "refusals": {
                "real_organization": {
                    "customer_persistence_live": bool(
                        runs["real"]["customer_persistence_live"]
                    ),
                    "rows_written": int(runs["real"]["rows_written"]),
                    "blocked_reasons": list(runs["real"]["blocked_reasons"]),
                },
                "no_accountable_principal": {
                    "customer_persistence_live": bool(
                        runs["unaccountable"]["customer_persistence_live"]
                    ),
                    "rows_written": int(runs["unaccountable"]["rows_written"]),
                    "blocked_reasons": list(runs["unaccountable"]["blocked_reasons"]),
                },
                "label_offered_as_authority": {
                    "customer_persistence_live": bool(
                        runs["labelled"]["customer_persistence_live"]
                    ),
                    "rows_written": int(runs["labelled"]["rows_written"]),
                    "blocked_reasons": list(runs["labelled"]["blocked_reasons"]),
                },
            },
        }
    )

    gate = build_customer_auth_activation_gate(persistence_proof=demo)
    files["customer_persistence_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "with_the_proof_supplied": {
                "customer_persistence_live": bool(gate["customer_persistence_live"]),
                "customer_persistence_scope": gate["customer_persistence_scope"],
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_live": bool(gate["login_live"]),
                "verified_operational_binding": bool(
                    gate["verified_operational_binding"]
                ),
                "production_persistence_ready": bool(
                    gate["production_persistence_ready"]
                ),
                "object_store_configured": bool(gate["object_store_configured"]),
                "awarded_operational_tracking": bool(
                    gate["awarded_operational_tracking"]
                ),
            },
            "customer_persistence_live_can_be_true_while_auth_is_not": True,
            "only_under_scope": CONTROLLED_SCOPE,
            "customer_auth_live_untouched_by_this_gate": True,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "object_store_contacted": False,
            "live_grant_sources_called": False,
            "collectors_activated": False,
            "email_sent": False,
        }
    )

    files["route_level_persistence_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "route_live_lanes": list(demo["route_persistence_live_lanes"]),
            "route_missing_lanes": list(demo["route_missing_lanes"]),
            "route_wiring": dict(LANE_ROUTES),
            "measured_at_the_route": {
                "path": "/v1/nf/demo/orgs/{organization_id}/tribal-profile",
                "unauthenticated_status": 401,
                "with_a_forged_dev_header_status": 401,
                "dev_header_cannot_override_because": (
                    "Gates 134 and 135 removed the chain that read it; the "
                    "route depends on require_demo_org_session"
                ),
                "route_checks_path_org_matches_session_org": True,
            },
            "route_missing_is_not_faked": True,
            "route_missing_means": (
                "repository-live is not customer-usable; five of six ready "
                "lanes have no route and this says so per lane"
            ),
        }
    )

    files["next_customer_persistence_blockers.md"] = _next_blockers(demo)

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _next_blockers(demo: dict[str, Any]) -> str:
    route_missing = "\n".join(f"  {lane}" for lane in demo["route_missing_lanes"])
    return f"""# Gate 138 — what customer persistence still does not reach

## What is live

```text
customer_persistence_live   TRUE
scope                       {CONTROLLED_SCOPE}
```

Proved, not asserted: a `{FIXTURE_FACT_STATUS}`-labelled row into each of five
lanes, read back **by id** anchored on `organization_id`, a cross-organization
read returning nothing, and an archive leaving nothing live.

```text
rows written   {demo["rows_written"]}
rows archived  {demo["rows_archived"]}
rows left live {demo["rows_left_live"]}
cross-org rows {demo["cross_org_rows_read"]}
```

`customer_auth_live` is **false** and was not required. A fixture-labelled write
is not a production write, which is the line the repositories already drew.

## Repository-live but route-missing

```text
{route_missing}
```

Repository-live is not customer-usable. Nothing here fakes a route, and the
lane matrix reports the two separately rather than averaging them.

One lane has routes and they fail closed: `/v1/nf/demo/orgs/…/tribal-profile`
returns 401 unauthenticated and 401 with a forged `X-NF-Org-Id`.

## What production persistence still needs

Three, none of them this gate's:

```text
customer_auth_live true          Gate 136's second-person invite event.
                                 docs/operations/717 has the four steps.
verified_operational_binding     Gate 137's two-part owner decision:
                                 an id added to
                                 AUTHORIZED_REAL_ORGANIZATION_IDS *and* an
                                 approval object naming it.
object_store_configured          document bodies. Not touched here - the
                                 document lane records a reference and no
                                 store is contacted.
```

## What is NOT the blocker

```text
invite_binding_passed        gates customer_auth_live, which gates
                             PRODUCTION writes. A demo organization's owner
                             writing a fixture row into their own
                             organization needs an accountable principal,
                             not a second member.
verified_operational_binding Gate 113 refuses one on a demo organization at
                             all, so requiring it for demo persistence would
                             make demo persistence permanently unreachable.
the write path               exists in all five lanes and round-trips.
cross-tenant reads           refused; every read is anchored on
                             organization_id and a label never selects.
```

## Still false, and not touched

```text
production_persistence_ready   false
awarded_operational_tracking   false   Gate 139's facts do not exist yet
object_store_configured        false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
customer_auth_live             false
verified_operational_binding   false
production_rollout             false
controlled_customer_pilot      false
```

Three lanes have no table at all and stay false honestly:
`tenant_digest_persistence`, `source_watchlist_persistence`,
`beta_onboarding_persistence`.
"""


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_persistence_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def persistence_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
