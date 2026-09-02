"""Gate 137F: what the binding path refuses, and what it has not activated.

Deterministic. The hermetic result is produced by running the real write path
against a temp database built here, so the artifact records a measurement rather
than a description — and it produces the same bytes every time because the
database is new, the ids are fixed, and no clock is read.

No secrets, no tokens, no cookies, no state, no PKCE verifier, no provider
subject, no customer data. A scan asserts it, and the scan discriminates a
credential FIELD carrying a value from a field NAMED in a refusal list — Gate
136F got that wrong and reported its own safeguard as a breach.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.tenant_customer_org_binding_repository_service import (
    AMBIGUOUS_ACTIVE,
    BINDINGS,
    DUPLICATE_ACTIVE,
    RESULT_FIELDS,
    VERIFIED_ALREADY_EXISTS,
    get_active_binding,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    APPROVAL_FIELDS,
    AUTHORIZED_REAL_ORGANIZATION_IDS,
    DEMO_ORGANIZATION_ID,
    FORBIDDEN_AUTHORITY_KEYS,
    NOT_APPROVED,
    PRODUCTION_SCOPE,
    REAL_ORG_SCOPE,
    REAL_ORGANIZATION_ID,
    REVOCATION_ENV,
    build_real_org_binding_activation_decision,
)
from nativeforge.services.verified_operational_binding_preparation_service import (
    CLASSIFICATION_SOURCE,
    write_invariant_failures,
    write_verified_operational_binding,
)

SCHEMA_VERSION = "nf_verified_operational_binding_gate137_artifact_v1"

ARTIFACT_DIR = "artifacts/verified_operational_binding_gate137"

ARTIFACT_FILES: tuple[str, ...] = (
    "verified_binding_survey.json",
    "demo_org_refusal.json",
    "real_org_activation_boundary.json",
    "hermetic_real_org_binding_result.json",
    "runtime_real_org_untouched.json",
    "customer_auth_readiness_after_gate137.json",
    "next_verified_binding_blockers.md",
)

#: A fixture organization that is neither the demo org nor the real one. Fixed
#: so the artifact is byte-stable, and distinct from both so the refusals stay
#: separately reachable.
FIXTURE_ORGANIZATION_ID = "cccccccc-dddd-eeee-ffff-000000000001"
FIXTURE_VERIFIER_ID = "dddddddd-eeee-ffff-0000-111111111111"
FIXTURE_BINDING_ID = uuid.UUID("eeeeeeee-ffff-0000-1111-222222222222")
FIXTURE_MOMENT = datetime(2026, 9, 2, tzinfo=UTC)

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


def _approval(organization_id: str, *, scope: str = REAL_ORG_SCOPE) -> dict[str, Any]:
    return {
        "organization_id": organization_id,
        "authorized_by": "mayhem",
        "authorization_scope": scope,
        "environment": "dev",
        "recorded_at": FIXTURE_MOMENT.isoformat(),
    }


def _hermetic_run() -> dict[str, Any]:
    """The real write path, against a database built for this call only.

    Three organizations, so all three outcomes are measured in one run rather
    than asserted from three descriptions:

    ```text
    the demo org      refused by classification
    aaaaaaaa-…        refused by name
    a fixture real org  written, read back, verified
    ```
    """
    engine = sa.create_engine("sqlite://")
    _ORGANIZATIONS.create(engine)
    BINDINGS.create(engine)

    outcomes: dict[str, Any] = {}
    with engine.begin() as connection:
        for organization_id, org_type in (
            (REAL_ORGANIZATION_ID, "real"),
            (DEMO_ORGANIZATION_ID, "demo"),
            (FIXTURE_ORGANIZATION_ID, "real"),
        ):
            connection.execute(
                sa.insert(_ORGANIZATIONS).values(
                    id=uuid.UUID(organization_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=FIXTURE_MOMENT,
                )
            )

        def attempt(
            label: str,
            organization_id: str,
            *,
            labels: str | None = None,
            **extra: Any,
        ) -> None:
            # `labels` separate from `label` because the duplicate case has to
            # reuse the SAME tenant and customer-org pair. The first version of
            # this derived both from `label`, so the "duplicate" attempt used
            # different labels, was not a duplicate, and wrote - while the
            # artifact beside it claimed duplicates were refused.
            pair = labels or label
            result = write_verified_operational_binding(
                connection=connection,
                binding_id=FIXTURE_BINDING_ID if label == "fixture_real_org" else None,
                created_at=FIXTURE_MOMENT,
                organization_id=organization_id,
                tenant_id=f"t-{pair}",
                customer_org_id=f"c-{pair}",
                verified_by_identity_id=FIXTURE_VERIFIER_ID,
                verified_at=FIXTURE_MOMENT.isoformat(),
                approval=_approval(organization_id),
                app_env="dev",
                **extra,
            )
            outcomes[label] = {
                "write_performed": bool(result["write_performed"]),
                "verified_operational_binding": bool(
                    result["verified_operational_binding"]
                ),
                "is_demo_derived": bool(result["is_demo_derived"]),
                "readback_performed": bool(result["readback_performed"]),
                "blocked_reasons": list(result["blocked_reasons"]),
                "invariant_failures": write_invariant_failures(result),
            }

        # The demo organization, with the caller insisting it is not one.
        attempt(
            "demo_org_with_is_demo_false",
            DEMO_ORGANIZATION_ID,
            is_demo=False,
            authorized_organization_ids=frozenset({DEMO_ORGANIZATION_ID}),
        )
        # The real organization, with a well-formed approval naming it.
        attempt("refused_real_org", REAL_ORGANIZATION_ID)
        # A fixture real organization, authorized.
        attempt(
            "fixture_real_org",
            FIXTURE_ORGANIZATION_ID,
            authorized_organization_ids=frozenset({FIXTURE_ORGANIZATION_ID}),
        )
        # The same organization and the same labels: the duplicate refusal.
        attempt(
            "fixture_real_org_again",
            FIXTURE_ORGANIZATION_ID,
            labels="fixture_real_org",
            authorized_organization_ids=frozenset({FIXTURE_ORGANIZATION_ID}),
        )
        # The same organization with DIFFERENT labels: refused too, by the
        # tighter rule. Two verified bindings for one organization contradict
        # each other whatever their labels say.
        attempt(
            "fixture_real_org_other_labels",
            FIXTURE_ORGANIZATION_ID,
            labels="fixture-other",
            authorized_organization_ids=frozenset({FIXTURE_ORGANIZATION_ID}),
        )

        rows = (
            connection.execute(
                sa.select(
                    BINDINGS.c.organization_id,
                    BINDINGS.c.binding_status,
                    BINDINGS.c.is_demo,
                )
            )
            .mappings()
            .all()
        )
        stored = sorted(
            (
                {
                    "organization_id": str(row["organization_id"]),
                    "binding_status": row["binding_status"],
                    "is_demo": bool(row["is_demo"]),
                }
                for row in rows
            ),
            # Dicts do not order themselves, and this has to be byte-stable.
            key=lambda entry: (entry["organization_id"], entry["binding_status"]),
        )
        readback = get_active_binding(
            connection=connection,
            organization_id=FIXTURE_ORGANIZATION_ID,
            tenant_id="t-fixture_real_org",
            customer_org_id="c-fixture_real_org",
        )

    engine.dispose()
    return {"outcomes": outcomes, "stored_rows": stored, "readback": readback}


def build_binding_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    run = _hermetic_run()
    outcomes = run["outcomes"]
    readback = run["readback"]

    files: dict[str, str] = {}

    files["verified_binding_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "137",
            "why_verified_operational_binding_was_false": (
                "verified_binding_workflow_service derives it as "
                "auth_live AND repository_write_performed AND "
                "production_verified_binding AND NOT demo_fixture; auth_live "
                "was false, and that was the only reason"
            ),
            "direction_of_the_dependency": (
                "verified_operational_binding requires customer_auth_live, not "
                "the reverse; it is not in REQUIRED_AUTH_GATES and adding it "
                "would close the cycle Gate 134F opened"
            ),
            "defects_found": [
                "prepare_insert took is_demo as a caller parameter and read no "
                "organization row, so a verified binding was written onto the "
                "demo organization with is_demo=False, production_verified_"
                "binding True, and every invariant passing",
                "the row landed in an RLS partition matching neither a demo "
                "session nor a real one",
                "verified_binding_workflow_service derived is_demo from the "
                "PRINCIPAL, so a principal's self-description chose an "
                "organization's partition",
                "no approval of any kind was required to write a verified "
                "binding for the real organization; authorization is role-based "
                "and checks no organization id",
                "two active verified bindings for one organization and label "
                "pair both wrote, and get_active_binding returned whichever "
                "came back first from an unordered query",
                "RESULT_FIELDS was declared in Gate 120B and consumed by "
                "nothing until this gate asserted it",
            ],
            "what_held_it_shut_before_this_gate": (
                "production_verified_binding_requires_live_customer_auth, and "
                "Gate 136 made customer_auth_live reachable"
            ),
            "is_demo_authority_now": CLASSIFICATION_SOURCE,
            "duplicate_refusal": DUPLICATE_ACTIVE,
            "second_verified_binding_refusal": VERIFIED_ALREADY_EXISTS,
            "ambiguous_read_refusal": AMBIGUOUS_ACTIVE,
            "result_fields_declared": list(RESULT_FIELDS),
            "modules_named_for_survey_that_do_not_exist": [
                "customer_identity_repository_service",
                "org_membership_repository_service",
                "customer_auth_current_user_service",
            ],
        }
    )

    demo_decision = build_real_org_binding_activation_decision(
        organization_id=DEMO_ORGANIZATION_ID,
        approval=_approval(DEMO_ORGANIZATION_ID),
        app_env="dev",
        org_type_in_database="demo",
        authorized_organization_ids=frozenset({DEMO_ORGANIZATION_ID}),
    )
    files["demo_org_refusal.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_organization_id": DEMO_ORGANIZATION_ID,
            "refused_even_when_listed_as_authorized": True,
            "refused_even_with_a_well_formed_approval": True,
            "refused_by": "organizations.org_type, read from the row",
            "not_refused_by": "a caller-supplied is_demo label",
            "boundary_decision": {
                "approves_real_org_binding_activation": bool(
                    demo_decision["approves_real_org_binding_activation"]
                ),
                "organization_is_demo": bool(demo_decision["organization_is_demo"]),
                "blocked_reasons": list(demo_decision["blocked_reasons"]),
            },
            "write_attempt_with_is_demo_false": outcomes["demo_org_with_is_demo_false"],
            "gate113_contract_weakened": False,
            "gate113_contract_strengthened_by": (
                "checking the organization rather than the label the caller "
                "supplied for it"
            ),
        }
    )

    real_decision = build_real_org_binding_activation_decision(
        organization_id=REAL_ORGANIZATION_ID,
        approval=_approval(REAL_ORGANIZATION_ID),
        app_env="dev",
        org_type_in_database="real",
    )
    files["real_org_activation_boundary.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "real_organization_id": REAL_ORGANIZATION_ID,
            "refused_by_name": True,
            "authorized_real_organization_ids": sorted(
                AUTHORIZED_REAL_ORGANIZATION_IDS
            ),
            "authorized_list_is_empty": not AUTHORIZED_REAL_ORGANIZATION_IDS,
            "authorized_list_is_empty_because": (
                "Mayhem's standing authorization refuses real org activation "
                "and refuses binding to this id by name"
            ),
            "approval_object_required": True,
            "approval_required_fields": list(APPROVAL_FIELDS),
            "approval_scopes": sorted({REAL_ORG_SCOPE, PRODUCTION_SCOPE}),
            "production_needs_its_own_scope": True,
            "revocation_environment_variable": REVOCATION_ENV,
            "grant_environment_variable": None,
            "no_environment_variable_can_approve": True,
            "forbidden_authority_keys": list(FORBIDDEN_AUTHORITY_KEYS),
            "not_approved": list(NOT_APPROVED),
            "decision_for_the_real_org": {
                "approves_real_org_binding_activation": bool(
                    real_decision["approves_real_org_binding_activation"]
                ),
                "approves_production_binding_activation": bool(
                    real_decision["approves_production_binding_activation"]
                ),
                "approves_production_rollout": bool(
                    real_decision["approves_production_rollout"]
                ),
                "blocked_reasons": list(real_decision["blocked_reasons"]),
            },
            "write_attempt_against_the_real_org": outcomes["refused_real_org"],
        }
    )

    files["hermetic_real_org_binding_result.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_organization_id": FIXTURE_ORGANIZATION_ID,
            "fixture_is_neither_the_demo_org_nor_the_real_one": True,
            "fixture_org_type": "real",
            "database": "in_memory_sqlite_built_for_this_call",
            "first_write": outcomes["fixture_real_org"],
            "second_write_same_labels": outcomes["fixture_real_org_again"],
            "second_write_other_labels": outcomes["fixture_real_org_other_labels"],
            "readback_by_organization_id": {
                "read_performed": bool(readback["read_performed"]),
                "rows_matched": int(readback["rows_matched"]),
                "binding_status": readback["binding_status"],
                "production_verified_binding": bool(
                    readback["production_verified_binding"]
                ),
                "demo_fixture": bool(readback["demo_fixture"]),
            },
            "stored_rows": run["stored_rows"],
            "proves": [
                "the verified binding write path works end to end",
                "is_demo is derived, and the row lands in the real partition",
                "the row can be read back by organization_id",
                "a second active binding for the same labels is refused",
                "a second active VERIFIED binding for the organization is "
                "refused whatever its labels say",
                "exactly one row exists afterwards",
            ],
            "does_not_prove": [
                "anything about the runtime real organization, which was not opened"
            ],
        }
    )

    files["runtime_real_org_untouched.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "real_organization_id": REAL_ORGANIZATION_ID,
            "runtime_database_opened_by_this_gate": False,
            "bindings_written_for_the_real_organization": 0,
            "bindings_written_for_the_demo_organization": 0,
            "rows_written_outside_the_hermetic_fixture": 0,
            "real_customer_data_written": False,
            "production_bindings_created": 0,
            "hermetic_fixture_database": "in_memory_sqlite, discarded",
            "how_this_is_known": (
                "every write in this gate went through an engine created in "
                "_hermetic_run and disposed at the end of it; the dev database "
                "is never addressed"
            ),
        }
    )

    readiness = build_customer_auth_activation_gate(
        verified_binding_readback=None,
        real_org_binding_activation_decision=real_decision,
    )
    files["customer_auth_readiness_after_gate137.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "deterministic_gate_no_evidence_supplied": {
                "login_live": bool(readiness["login_live"]),
                "customer_auth_live": bool(readiness["customer_auth_live"]),
                "verified_operational_binding": bool(
                    readiness["verified_operational_binding"]
                ),
                "production_write_readiness": bool(
                    readiness["production_write_readiness"]
                ),
                "customer_auth_live_scope": readiness["customer_auth_live_scope"],
            },
            "verified_operational_binding_in_required_auth_gates": False,
            "verified_operational_binding_in_required_auth_gates_because": (
                "it is not; the dependency runs the other way and adding it "
                "would be a cycle"
            ),
            "what_consumes_verified_operational_binding": [
                "award_requirements_repository_service: a production "
                "requirement write is refused without one"
            ],
            "customer_auth_live_is_not_production_readiness": True,
            "production_write_readiness_requires": list(
                readiness["production_write_readiness_requires"]
            ),
            "production_rollout": False,
            "controlled_customer_pilot": False,
        }
    )

    files["next_verified_binding_blockers.md"] = _next_blockers()

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            # A key with a value after it. A field NAMED in a refusal list is
            # the safeguard being documented, which is what Gate 136F's first
            # scan could not tell apart.
            if re.search(rf'"{re.escape(field)}"\s*:\s*"', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _next_blockers() -> str:
    return f"""# Gate 137 — what still blocks a verified operational binding

## Runtime value

```text
verified_operational_binding   FALSE
```

Not surfaced by `/api/auth/session` before this gate and reported there now,
beside `customer_auth_live` rather than inside it.

## Two blockers, in order, and neither is code

### 1. `customer_auth_live`

`verified_binding_workflow_service` refuses a production verified binding
without it:

```text
production_verified_binding_requires_live_customer_auth
```

Gate 136 made this reachable. It needs a second real Google account to complete
an invite — `docs/operations/717` has the four steps and the OAuth test-user
prerequisite.

### 2. An owner decision authorizing real-org binding activation

```text
AUTHORIZED_REAL_ORGANIZATION_IDS = frozenset()
```

Empty, deliberately. Mayhem's standing authorization refuses `real org
activation` and refuses binding to `{REAL_ORGANIZATION_ID}` by name.

Activating one needs **both**:

```text
a reviewed code change adding the id to that constant
an approval object naming the same organization, scope, environment and
  who authorized it
```

Either alone is refused. No environment variable can approve; one can revoke.

## What is NOT the blocker any more

```text
the write path            exists, and is proved end to end against a
                          hermetic real organization
is_demo                   derived from organizations.org_type
duplicates                refused
ambiguous reads           refused rather than resolved by row order
the demo organization     refused by classification, in the boolean and in
                          the blocker list
```

## What is still open, and named rather than fixed

Binder authorization decides by **role** — `{{platform_admin, tenant_admin}}` —
and reads `org_claim_verified` off the principal. Gate 132's membership
evidence and Gate 136's invite evidence both read real rows, and neither is an
input to that decision.

So the strongest membership facts in the system do not reach the decision that
writes a verified binding. Recorded in `719` and named here as the next gate's
work; the preparation service reports `membership_source: not_consulted` rather
than implying otherwise.

## Still false, and not touched by this gate

```text
production_rollout             false
controlled_customer_pilot      false
customer_auth_live             false
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```
"""


def write_binding_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_binding_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def binding_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
