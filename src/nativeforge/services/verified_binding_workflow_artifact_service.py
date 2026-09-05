"""Verified binding workflow artifacts (Gate 120G).

Four files describing the repository, the workflow, and what none of it makes
true. Written to `artifacts/verified_binding_workflow/`.

```text
tenant_customer_org_binding_repository_contract.json  operations, rules, columns
verified_binding_workflow_matrix.csv                  eight cases, one row each
verified_binding_workflow_demo_fixtures.json          the fixture set entire
verified_binding_readiness_summary.md                 what none of it permits
```

## No customer data reaches a file, and it is checked three ways

```text
1. by field name   a nested walk refuses any payload carrying a field named
                   like an email, a subject, a token or a session
2. by fixture value  the payload is scanned for the fixture tenant and
                   customer-org labels appearing anywhere they should not
3. by env value    Gate 115's scanner looks for every configured OIDC_* value
```

The fixture labels are not secrets — they are committed constants prefixed
`nf-demo-fixture-` and they name nobody. They appear in the artifacts on
purpose, as labels. The scan checks they appear *only* as labels and never as an
`organization_id`, which is the substitution Gates 110–113 exist to refuse.

## The matrix is a CSV because it is a table of cases

Eight rows, one per fixture case, each carrying what the workflow decided at
every step. A reader scanning for a green line finds
`verified_operational_binding` false on all eight.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_verified_binding_workflow_artifact_v1"

ARTIFACT_DIR = "artifacts/verified_binding_workflow"

# Claims that must always carry the same value, whatever is measured.
FIXED_CLAIMS: dict[str, bool] = {
    "binding_repository_contract_available": True,
    "binding_repository_write_path_available": True,
    "binding_table_schema_available": True,
    "verified_binding_workflow_available": True,
    "verified_operational_binding": False,
    "customer_auth_live": False,
    "login_live": False,
    "customer_persistence_live": False,
    "beta_onboarding_ready": False,
    "production_rollout_ready": False,
    "source_monitoring_live": False,
    "source_coverage_claimed": False,
}

# Counts that must always be zero.
FIXED_COUNTS: dict[str, int] = {
    "production_verified_bindings_created": 0,
    "real_customer_rows_written": 0,
    "rows_in_the_application_database": 0,
}

# Field names that would mean customer data had entered an artifact.
FORBIDDEN_VALUE_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "email_address",
        "subject",
        "session_cookie_value",
        "cookie_value",
        "signing_key",
        "client_secret",
        "access_token",
        "id_token",
        "refresh_token",
        "state_value",
        "code_verifier",
    }
)

MATRIX_COLUMNS: tuple[str, ...] = (
    "case",
    "operation",
    "binding_operation",
    "authorization_checked",
    "authorization_allowed",
    "binding_contract_valid",
    "repository_write_allowed",
    "repository_write_performed",
    "verified_operational_binding",
    "customer_auth_live",
    "human_review_required",
    "rows_written",
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


def scan_for_label_as_anchor(payload: Any) -> list[str]:
    """Did a tenant or customer-org label end up somewhere only a UUID belongs?

    The substitution Gates 110-113 exist to refuse, checked at the point where
    it would become a committed claim. A label in an `organization_id` field is
    a label being treated as an RLS authority.
    """
    from nativeforge.services.verified_binding_workflow_demo_fixture_service import (
        FIXTURE_PREFIX,
    )

    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"organization_id", "rls_anchor"} and isinstance(value, str):
                    if value.startswith(FIXTURE_PREFIX):
                        found.add(f"label_used_as_{key}")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def build_repository_contract() -> dict[str, Any]:
    """The repository's operations and rules, with no row in it."""
    from nativeforge.services.tenant_customer_org_binding_repository_service import (
        BINDINGS,
        READ_OPERATIONS,
        REPOSITORY_OPERATIONS,
        TABLE_NAME,
        WRITE_OPERATIONS,
    )
    from nativeforge.services.tenant_customer_org_binding_store_service import (
        FORBIDDEN_ANCHOR_NAMES,
        RLS_ANCHOR_COLUMN,
        STORABLE_BINDING_STATUSES,
        VERIFIER_REQUIRED_STATUSES,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "migration_revision": "0029",
            # The live head, not this gate's migration. Gate 127 added 0035.
            "alembic_head": "0041",
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
            "storable_binding_statuses": sorted(STORABLE_BINDING_STATUSES),
            "verifier_required_statuses": sorted(VERIFIER_REQUIRED_STATUSES),
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": bool(column.nullable),
                }
                for column in BINDINGS.columns
            ],
            "column_count": len(BINDINGS.columns),
            "check_constraints": sorted(
                c.name
                for c in BINDINGS.constraints
                if c.name and str(c.name).startswith("ck_")
            ),
            "rules": [
                "organization_id is required and must be UUID-shaped",
                "tenant_id and customer_org_id are labels and never select alone",
                "organization_profile_id is refused, not ignored",
                "a verified binding requires a verifier identity and a timestamp",
                "a demo fixture binding may carry neither",
                "a conflicting binding authorizes no operational write",
                "revocation is an UPDATE; nothing is ever deleted",
                "contract mode is the default and touches no database",
            ],
            **{k: v for k, v in FIXED_COUNTS.items()},
        }
    )


def render_workflow_matrix(fixture: dict[str, Any]) -> str:
    """One row per fixture case. A reader scanning for green finds none."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    for row in fixture["cases"]:
        writer.writerow(
            [
                row["case"],
                row["operation"],
                row["binding_operation"],
                str(row["authorization_checked"]).lower(),
                str(row["authorization_allowed"]).lower(),
                str(row["binding_contract_valid"]).lower(),
                str(row["repository_write_allowed"]).lower(),
                str(row["repository_write_performed"]).lower(),
                str(row["verified_operational_binding"]).lower(),
                str(row["customer_auth_live"]).lower(),
                str(row["human_review_required"]).lower(),
                row["rows_written"],
                "; ".join(row["blocked_reasons"]),
            ]
        )
    return buffer.getvalue()


def build_workflow_declaration() -> dict[str, Any]:
    """What Gate 120 built, and the claims it does not make."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )

    gate = build_customer_auth_activation_gate()
    readiness = build_binding_store_readiness()
    matrix = build_capability_matrix()
    binding_lane = next(
        row
        for row in matrix["rows"]
        if row["capability"] == "identity_binding_persistence"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_auth_gate_count": len(REQUIRED_AUTH_GATES),
            "missing_auth_gates": [
                name for name in REQUIRED_AUTH_GATES if not gate.get(name)
            ],
            "binding_lane_schema_available": bool(binding_lane["schema_available"]),
            "binding_lane_repository_available": bool(
                binding_lane["repository_available"]
            ),
            "binding_lane_write_path_available": bool(
                binding_lane["write_path_available"]
            ),
            "binding_lane_operational": bool(binding_lane["operational"]),
            "binding_store_writable": bool(readiness["store_writable"]),
            "operational_binding_storage_ready": bool(
                readiness["operational_binding_storage_ready"]
            ),
            **FIXED_CLAIMS,
            **FIXED_COUNTS,
        }
    )


def render_readiness_summary() -> str:
    """What Gate 120 moved, and the sentence to refuse."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        REQUIRED_AUTH_GATES,
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.verified_binding_workflow_demo_fixture_service import (
        build_workflow_demo_fixture_set,
    )

    gate = build_customer_auth_activation_gate()
    fixture = build_workflow_demo_fixture_set()
    missing = [name for name in REQUIRED_AUTH_GATES if not gate.get(name)]

    lines = [
        "# Verified binding workflow readiness (Gate 120)",
        "",
        "## The sentence to refuse",
        "",
        '> "The binding repository exists, so tenants can be bound."',
        "",
        "A repository is somewhere to put a verified binding. A verified binding",
        "names the identity that verified it, and `verified_by_identity_id`",
        "references `nf_identities` — a verified OIDC subject. No OIDC subject",
        f"can be verified while {len(missing)} of {len(REQUIRED_AUTH_GATES)} "
        "activation gates are",
        "unsatisfied, so no verifier identity exists to name.",
        "",
        "A production verified binding is not merely unauthorized today. It is",
        "unconstructible.",
        "",
        "## What moved",
        "",
        "```text",
        "binding repository            none          six operations, DB-backed",
        "verified binding workflow     none          authorization -> contract",
        "                                            -> repository, in that order",
        "write_allowed                 unconsumed    acted on",
        "identity_binding lane repo    false         true",
        "identity_binding write path   false         true",
        "revocation                    a dict        an UPDATE that keeps the row",
        "```",
        "",
        "## What did not move",
        "",
        "```text",
    ]
    for name in (
        "verified_operational_binding",
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        lines.append(f"{name:44s}{str(FIXED_CLAIMS[name]).lower()}")
    for name, value in FIXED_COUNTS.items():
        lines.append(f"{name:44s}{value}")
    lines.extend(
        [
            "```",
            "",
            "## The unsatisfied gates",
            "",
            "```text",
        ]
    )
    lines.extend(missing)
    lines.extend(
        [
            "```",
            "",
            "## The fixture set",
            "",
            "```text",
            f"cases                          {fixture['case_count']}",
            f"authorized                     {fixture['authorized_count']}",
            f"repository writes performed    {fixture['write_performed_count']}",
            f"operational bindings produced  {fixture['operational_binding_count']}",
            f"production verified bindings   "
            f"{fixture['production_verified_bindings_created']}",
            f"real customer rows written     {fixture['real_customer_rows_written']}",
            "```",
            "",
            "Four of eight cases write a row. Every one of those rows is a demo",
            "fixture in an in-memory database that is discarded when the case",
            "ends, and none of them is an operational binding.",
            "",
            "## Why no API route",
            "",
            "```text",
            "1  a read route needs a session to scope by, and /current-user",
            "   401s for everybody, so the permitted branch is unreachable",
            "2  the table is empty, so the route's only behaviour is refusal",
            "3  a route is a surface, and the first thing to exercise it would",
            "   be a real browser with a real cookie",
            "```",
            "",
            "Recorded in doc 652 as a decision rather than left as an omission.",
            "",
            "## What the next gate needs",
            "",
            "```text",
            "1. customer auth activation   11 of 16 gates. Everything below",
            "                              waits on this and nothing else does.",
            "",
            "2. a verifier identity        an nf_identities row from a verified",
            "                              OIDC subject",
            "",
            "3. a database with 0029       store_writable is false: the",
            "                              migration is defined and no runtime",
            "                              database has applied it",
            "",
            "4. the remaining six lanes    each needs a repository of its own",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_workflow_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all four artifacts. Refuses if anything forbidden appears."""
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )
    from nativeforge.services.verified_binding_workflow_demo_fixture_service import (
        build_workflow_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR

    contract = build_repository_contract()
    fixture = build_workflow_demo_fixture_set()
    declaration = build_workflow_declaration()

    contents = {
        "tenant_customer_org_binding_repository_contract.json": json.dumps(
            contract, indent=2, sort_keys=True
        )
        + "\n",
        "verified_binding_workflow_matrix.csv": render_workflow_matrix(fixture),
        "verified_binding_workflow_demo_fixtures.json": json.dumps(
            {"declaration": declaration, "fixture": fixture},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "verified_binding_readiness_summary.md": render_readiness_summary(),
    }

    blob = "".join(contents.values())
    payloads = [contract, fixture, declaration]

    credential_fields = sorted(
        {field for payload in payloads for field in scan_for_credential_fields(payload)}
    )
    if credential_fields:
        raise ValueError(
            f"refusing to write: credential field names present {credential_fields}"
        )

    label_anchors = sorted(
        {found for payload in payloads for found in scan_for_label_as_anchor(payload)}
    )
    if label_anchors:
        raise ValueError(f"refusing to write: {label_anchors}")

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
            "label_anchors_found": label_anchors,
            "configured_secret_values_found": env_secrets,
        }
    )


def workflow_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What a written artifact set must never be able to claim."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if result.get("file_count") != 4:
        fails.append("expected_four_artifacts")

    for field in (
        "credential_fields_found",
        "label_anchors_found",
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

    if declaration.get("binding_lane_operational"):
        fails.append("declaration_claims_the_binding_lane_is_operational")

    return sorted(set(fails))
