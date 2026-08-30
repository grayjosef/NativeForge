"""Tenant profile persistence artifacts (Gate 123G).

Four files describing the repository, what it validates, and what none of it
makes true. Written to `artifacts/tenant_profile_persistence/`.

```text
tenant_profile_repository_contract.json      operations, columns, rules
tenant_profile_validation_matrix.csv         one row per validation case
tenant_profile_persistence_demo_fixtures.json  the ten cases
tenant_profile_persistence_readiness_summary.md  what remains blocked
```

## Two scans, and one of them is specific to this gate

```text
1  by field name    a nested walk for anything named like real tenant data
2  by inference     any result claiming an inference this campaign prohibits
```

The second is the one that matters here. A tenant profile artifact is *made of*
claims about a real government — recognition status, operating states, applicant
classes — and the danger is not a leaked credential but a fabricated fact. Any
payload carrying `recognition_status_inferred`, `operating_states_inferred` or
`mailing_address_considered` refuses the write.

## No real tenant appears

Every organization id is a fixed fixture UUID, every label carries the
`nf-demo-fixture-` prefix, and every fact status is `demo_fixture` — which is
deliberately outside `ACTIONABLE_FACT_STATUSES`, so nothing in these files can
drive a decision even if something read them.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_profile_persistence_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_profile_persistence"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "tenant_profile_repository_available": True,
    "tenant_profile_validation_available": True,
    "tenant_profile_schema_available": True,
    "tenant_profile_operational": False,
    "customer_auth_live": False,
    "login_live": False,
    "verified_operational_binding": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "operating_states_inferred_from_address": False,
    "recognition_status_inferred": False,
}

FIXED_COUNTS: dict[str, int] = {
    "production_tenant_profiles_created": 0,
    "real_customer_data_written": 0,
    "rows_deleted": 0,
    "rows_in_the_application_database": 0,
}

# Field names that would mean real tenant data had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "uei",
        "ein",
        "sam_registration_status",
        "physical_address",
        "mailing_address",
        "authorized_representative",
        "finance_contact",
        "email",
        "client_secret",
        "signing_key",
        "session_cookie_value",
    }
)

# A result claiming any of these has inferred something this campaign refuses to
# infer. The check exists because a tenant profile artifact is made of claims
# about a real government.
FORBIDDEN_INFERENCE_FLAGS: frozenset[str] = frozenset(
    {
        "recognition_status_inferred",
        "operating_states_inferred",
        "operating_states_inferred_from_address",
        "applicant_class_inferred",
        "priorities_inferred",
        "mailing_address_considered",
        "fabricated",
    }
)

MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "recognition_status_known",
    "operating_states_valid",
    "state_source_matching_enabled",
    "applicant_classes_present",
    "digest_frequency_valid",
    "routing_rules_valid",
    "profile_ready_for_matching",
    "human_review_required",
    "unknown_fields",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def scan_for_credential_fields(payload: Any) -> list[str]:
    """Which forbidden field names appear anywhere. Names, never values."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_VALUE_FIELDS:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def scan_for_claimed_inferences(payload: Any) -> list[str]:
    """Did anything claim an inference this campaign refuses to make?

    The check this gate needed. A leaked credential is not the danger in a
    tenant profile artifact; a fabricated fact about a real government is.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_INFERENCE_FLAGS and bool(value) is True:
                    found.add(f"claimed_inference:{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def build_repository_contract() -> dict[str, Any]:
    """The repository's operations and rules, with no profile in it."""
    from nativeforge.services.tenant_beta_profile_service import (
        ACTIONABLE_FACT_STATUSES,
        APPLICANT_CLASSES,
        DIGEST_FREQUENCIES,
        FACT_STATUSES,
        RECOGNITION_STATUSES,
    )
    from nativeforge.services.tenant_profile_repository_service import (
        FORBIDDEN_ANCHOR_NAMES,
        PROFILE_STATUSES,
        READ_OPERATIONS,
        REPOSITORY_OPERATIONS,
        RLS_ANCHOR_COLUMN,
        TABLE_NAME,
        TENANT_BETA_PROFILES,
        WRITE_OPERATIONS,
        prohibited_inferences,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0031",
            "alembic_head": "0031",
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', "
                "true)::uuid AND is_demo = "
                "current_setting('app.current_org_is_demo', true)::boolean"
            ),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "operations": sorted(REPOSITORY_OPERATIONS),
            "write_operations": sorted(WRITE_OPERATIONS),
            "read_operations": sorted(READ_OPERATIONS),
            "recognition_statuses": sorted(RECOGNITION_STATUSES),
            "applicant_classes": sorted(APPLICANT_CLASSES),
            "digest_frequencies": sorted(DIGEST_FREQUENCIES),
            "fact_statuses": sorted(FACT_STATUSES),
            "actionable_fact_statuses": sorted(ACTIONABLE_FACT_STATUSES),
            "profile_statuses": sorted(PROFILE_STATUSES),
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": bool(column.nullable),
                }
                for column in TENANT_BETA_PROFILES.columns
            ],
            "column_count": len(TENANT_BETA_PROFILES.columns),
            "check_constraints": sorted(
                c.name
                for c in TENANT_BETA_PROFILES.constraints
                if c.name and str(c.name).startswith("ck_")
            ),
            "prohibited_inferences": prohibited_inferences(),
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "tenant_id_label and customer_org_id_label are labels and "
                "never select a row",
                "organization_profile_id is refused, not ignored",
                "operating_states drives state matching; a service area or a "
                "mailing address never does",
                "an unknown recognition status may only carry an unestablished "
                "fact status",
                "archive by setting archived_at; nothing is ever deleted",
                "a production write requires customer_auth_live and a verified "
                "operational binding",
                "demo fixture writes are storable and never actionable",
            ],
            **{k: v for k, v in FIXED_COUNTS.items()},
        }
    )


def build_validation_cases() -> list[dict[str, Any]]:
    """The validation cases the matrix renders. Fixture inputs only."""
    return [
        {
            "case": "complete_sc_profile",
            "profile": {
                "recognition_status": "state_recognized",
                "recognition_status_fact_status": "tenant_supplied",
                "operating_states": ["SC"],
                "operating_states_fact_status": "tenant_supplied",
                "service_area": "the Pee Dee region",
                "applicant_classes": ["state_recognized_tribe"],
                "applicant_classes_fact_status": "tenant_supplied",
                "priority_topics": ["housing"],
                "excluded_topics": ["defense"],
                "digest_frequency": "weekly",
                "routing_rules": ["grants_admin"],
                "source_watchlist_preferences": ["sc_state_portal"],
            },
        },
        {
            "case": "empty_profile",
            "profile": {},
        },
        {
            "case": "unknown_recognition_status",
            "profile": {
                "recognition_status": "unknown",
                "recognition_status_fact_status": "unknown",
                "operating_states": ["SC"],
                "operating_states_fact_status": "tenant_supplied",
                "applicant_classes": ["state_recognized_tribe"],
                "applicant_classes_fact_status": "tenant_supplied",
                "priority_topics": ["housing"],
                "digest_frequency": "weekly",
                "routing_rules": ["grants_admin"],
                "source_watchlist_preferences": ["sc_state_portal"],
            },
        },
        {
            "case": "service_area_without_operating_states",
            "profile": {
                "recognition_status": "state_recognized",
                "recognition_status_fact_status": "tenant_supplied",
                "operating_states": [],
                "service_area": "1 Main Street, Columbia, South Carolina",
                "applicant_classes": ["state_recognized_tribe"],
                "applicant_classes_fact_status": "tenant_supplied",
                "priority_topics": ["housing"],
                "digest_frequency": "weekly",
                "routing_rules": ["grants_admin"],
                "source_watchlist_preferences": ["sc_state_portal"],
            },
        },
        {
            "case": "demo_fixture_facts_are_not_actionable",
            "profile": {
                "recognition_status": "state_recognized",
                "recognition_status_fact_status": "demo_fixture",
                "operating_states": ["SC"],
                "operating_states_fact_status": "demo_fixture",
                "applicant_classes": ["state_recognized_tribe"],
                "applicant_classes_fact_status": "demo_fixture",
                "priority_topics": ["housing"],
                "digest_frequency": "weekly",
                "routing_rules": ["grants_admin"],
                "source_watchlist_preferences": ["sc_state_portal"],
            },
        },
        {
            "case": "topic_both_prioritised_and_excluded",
            "profile": {
                "recognition_status": "state_recognized",
                "recognition_status_fact_status": "tenant_supplied",
                "operating_states": ["SC"],
                "operating_states_fact_status": "tenant_supplied",
                "applicant_classes": ["state_recognized_tribe"],
                "applicant_classes_fact_status": "tenant_supplied",
                "priority_topics": ["housing"],
                "excluded_topics": ["housing"],
                "digest_frequency": "weekly",
                "routing_rules": ["grants_admin"],
                "source_watchlist_preferences": ["sc_state_portal"],
            },
        },
    ]


def render_validation_matrix(matrix: dict[str, Any]) -> str:
    """One row per validation case."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    for row in matrix["rows"]:
        writer.writerow(
            [
                row["case"],
                str(row["recognition_status_known"]).lower(),
                str(row["operating_states_valid"]).lower(),
                str(row["state_source_matching_enabled"]).lower(),
                str(row["applicant_classes_present"]).lower(),
                str(row["digest_frequency_valid"]).lower(),
                str(row["routing_rules_valid"]).lower(),
                str(row["profile_ready_for_matching"]).lower(),
                str(row["human_review_required"]).lower(),
                "; ".join(row["unknown_fields"]),
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_persistence_declaration() -> dict[str, Any]:
    """What Gate 123 built, and the claims it does not make."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    gate = build_customer_auth_activation_gate()
    beta = build_tenant_beta_readiness()
    matrix = build_capability_matrix()
    lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "tenant_profile_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_profile_write_path_available": bool(lane["write_path_available"]),
            "tenant_profile_lane_operational": bool(lane["operational"]),
            "tenant_beta_profile_repository_available": bool(
                lane["tenant_beta_profile_repository_available"]
            ),
            "tenant_beta_profile_table": lane["tenant_beta_profile_table"],
            "tenant_beta_profiles_stored": int(beta["tenant_beta_profiles_stored"]),
            "missing_auth_gates": list(gate["missing_auth_gates"]),
            "activation_blocker_names": list(gate["activation_blocker_names"]),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 123 moved, and the sentence to refuse."""
    from nativeforge.services.tenant_profile_persistence_demo_fixture_service import (
        build_tenant_profile_fixture_set,
    )

    fixture = build_tenant_profile_fixture_set()
    declaration = build_persistence_declaration()

    lines = [
        "# Tenant profile persistence readiness (Gate 123)",
        "",
        "## The sentence to refuse",
        "",
        '> "Tenant profiles are repository-backed, so beta onboarding can start."',
        "",
        "The repository exists and the table holds zero rows. A production",
        "profile write needs `customer_auth_live` and a verified operational",
        "binding, and both are false. A row asserting a tenant's recognition",
        "status while nobody can be authenticated as that tenant is a",
        "fabricated fact in a table, which is worse than an empty table.",
        "",
        "## Two profiles, and this gate built the second",
        "",
        "```text",
        "nf_tribal_profiles       who this Tribe is when a form is submitted",
        "                         UEI, EIN, SAM, addresses, contacts, narratives",
        "                         table since 0003",
        "",
        "nf_tenant_beta_profiles  how this tenant wants NativeForge to behave",
        "                         recognition, operating states, applicant",
        "                         classes, watchlist, digest, routing, alerts",
        "                         table as of 0031",
        "```",
        "",
        "Gate 123A found the two share not one column. The Gate 103 contract",
        "already carried every field this gate needed and had nowhere to put",
        "them.",
        "",
        "## What moved",
        "",
        "```text",
        "tenant beta profile table       none      migration 0031, 8 CHECKs",
        "tenant beta profile repository  none      6 operations",
        "profile validation              none      11 checks, 4 refusals",
        "state source matching           implicit  driven by operating_states",
        "alembic head                    0030      0031",
        "```",
        "",
        "## What did not move",
        "",
        "```text",
    ]
    for name in (
        "tenant_profile_operational",
        "customer_auth_live",
        "login_live",
        "verified_operational_binding",
        "customer_persistence_live",
        "beta_onboarding_ready",
        "production_rollout_ready",
    ):
        lines.append(f"{name:44s}{str(FIXED_CLAIMS[name]).lower()}")
    for name, value in FIXED_COUNTS.items():
        lines.append(f"{name:44s}{value}")
    lines.extend(
        [
            "```",
            "",
            "## operating_states decides; an address never does",
            "",
            "```text",
            'operating_states ["SC"]                      -> SC sources match',
            'service_area "the Pee Dee region"            -> matches nothing',
            'service_area "Columbia, South Carolina"      -> matches nothing',
            "```",
            "",
            "The third line is the one worth reading twice. South Carolina is",
            "written in the text and no South Carolina source matches, because",
            "an address is not an operating state. Gate 103 named that refusal;",
            "this gate is the first thing to enforce it against stored data.",
            "",
            "A tenant may operate, serve and be eligible in a state it is not",
            "headquartered in. Deriving the second from the first would produce",
            "a plausible answer and the wrong one.",
            "",
            "## Unknown stays unknown",
            "",
            "```text",
            "unknown             nobody has established this",
            "needs_human_review  somebody looked and could not settle it",
            "verified            established by evidence",
            "tenant_supplied     the tenant told us and we have not checked",
            "demo_fixture        a fixture value, never actionable",
            "```",
            "",
            "`demo_fixture` is deliberately outside the actionable set. Every",
            "profile in the fixture file is storable and none is actionable,",
            "which is the distinction the status vocabulary exists to make.",
            "",
            "The database enforces the sharpest case: an unknown recognition",
            "status may only carry an unestablished fact status, so a guess",
            "cannot be stored as an established fact.",
            "",
            "## The fixture set",
            "",
            "```text",
            f"cases                        {fixture['case_count']}",
            f"storable                     {fixture['storable_count']}",
            f"production writes permitted  {fixture['production_write_count']}",
            f"production profiles created  "
            f"{fixture['production_tenant_profiles_created']}",
            f"rows deleted                 {fixture['rows_deleted']}",
            "```",
            "",
            "## Why no API route",
            "",
            "```text",
            "1  a read route needs a session to scope by, and /current-user",
            "   401s for everybody",
            "2  the table holds zero rows, so the route's only behaviour is",
            "   no_profile",
            "3  four tribal-profile routes already exist behind the dev header;",
            "   a fifth on a different dependency would leave two profile",
            "   surfaces with two different auth stories",
            "```",
            "",
            "The third is specific to this gate and is the strongest.",
            "",
            "## What the next gate needs",
            "",
            "```text",
            "1. customer auth activation   the 11 gates from Gate 121, none of",
            "                              which is code",
            "2. a verified operational     the Gate 120 workflow, once a",
            "   binding                    verifier identity can exist",
            "3. then the first profile     written through this repository, by",
            "                              a tenant admin who can be",
            "                              authenticated as one",
            "```",
            "",
        ]
    )
    _ = declaration
    return "\n".join(lines)


def write_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.tenant_profile_persistence_demo_fixture_service import (
        build_tenant_profile_fixture_set,
    )
    from nativeforge.services.tenant_profile_persistence_validation_service import (
        build_validation_matrix,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    matrix = build_validation_matrix(cases=build_validation_cases())
    fixture = build_tenant_profile_fixture_set()
    declaration = build_persistence_declaration()

    contents = {
        "tenant_profile_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "tenant_profile_validation_matrix.csv": render_validation_matrix(matrix),
        "tenant_profile_persistence_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "tenant_profile_persistence_readiness_summary.md": (render_readiness_summary()),
    }

    blob = "".join(contents.values())
    payloads = [contract, matrix, fixture, declaration]

    credential_fields = sorted(
        {field for payload in payloads for field in scan_for_credential_fields(payload)}
    )
    if credential_fields:
        raise ValueError(
            f"refusing to write: forbidden field names present {credential_fields}"
        )

    claimed_inferences = sorted(
        {
            found
            for payload in payloads
            for found in scan_for_claimed_inferences(payload)
        }
    )
    if claimed_inferences:
        raise ValueError(f"refusing to write: {claimed_inferences}")

    env_secrets = scan_for_secret_values(blob)
    if env_secrets:
        raise ValueError(
            f"refusing to write: configured secret values present {env_secrets}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, text in contents.items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written[name] = str(path)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": str(out_dir),
            "files_written": written,
            "file_count": len(written),
            "declaration": declaration,
            "credential_fields_found": credential_fields,
            "claimed_inferences_found": claimed_inferences,
            "configured_secret_values_found": env_secrets,
        }
    )


def persistence_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 4:
        fails.append("expected_four_artifacts")

    for field in (
        "credential_fields_found",
        "claimed_inferences_found",
        "configured_secret_values_found",
    ):
        if result.get(field):
            fails.append(f"artifacts_written_with_{field}")

    declaration = dict(result.get("declaration") or {})
    for claim, expected in FIXED_CLAIMS.items():
        if claim not in declaration:
            fails.append(f"declaration_missing_claim:{claim}")
        elif bool(declaration[claim]) is not expected:
            fails.append(f"fixed_claim_changed:{claim}")

    for count, expected_count in FIXED_COUNTS.items():
        if declaration.get(count) != expected_count:
            fails.append(f"fixed_count_changed:{count}")

    if not declaration.get("missing_auth_gates"):
        fails.append("declaration_claims_every_activation_gate_is_satisfied")

    if declaration.get("tenant_profile_lane_operational"):
        fails.append("declaration_claims_the_tenant_profile_lane_is_operational")

    if declaration.get("tenant_beta_profiles_stored"):
        fails.append("declaration_claims_a_profile_is_stored")

    return sorted(set(fails))
