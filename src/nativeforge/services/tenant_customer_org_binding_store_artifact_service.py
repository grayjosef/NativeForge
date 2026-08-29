"""Binding store artifacts (Gate 113H).

Five files describing what the binding store is, what it refuses, and what it
still cannot do. Written to `artifacts/tenant_customer_org_binding_store/`.

```text
tenant_customer_org_binding_store_contract.json    what the store is and enforces
tenant_customer_org_binding_store_matrix.csv       nine cases and their verdicts
tenant_customer_org_binding_store_demo_fixtures.json  the fixture set entire
membership_organization_id_wiring.csv              which lookups take which id
tenant_customer_org_binding_store_readiness.md     what it does not yet permit
```

## The readiness summary is the one somebody will quote

So it leads with the refusals rather than closing with them. "The binding store
exists" is a true sentence that becomes false the moment somebody appends "so
customer bindings can be stored now" — and that append is exactly what a summary
ending on a positive note invites.

## Everything is regenerated, nothing is transcribed

Each artifact is rendered from the service that owns the fact. Nothing here
restates a value that lives elsewhere, so a committed artifact that disagrees
with the code is a test failure rather than a stale file nobody noticed.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_customer_org_binding_store_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_customer_org_binding_store"

# The membership lookups Gate 113D touched, and the identity each one takes.
# Rendered as an artifact because "which name reaches which column" is the fact
# this gate exists to fix, and a table of it is the shortest proof it was fixed.
MEMBERSHIP_WIRING: tuple[tuple[str, str, str, str], ...] = (
    (
        "postgres_membership_directory.lookup_membership",
        "organization_id",
        "nf_org_memberships.organization_id (uuid)",
        "renamed_by_gate_113",
    ),
    (
        "postgres_membership_directory.resolve_persisted_membership",
        "organization_id",
        "forwarded to lookup_membership",
        "renamed_by_gate_113",
    ),
    (
        "postgres_membership_directory.resolve_persisted_membership",
        "organization_profile_id",
        "refused unless uuid-shaped",
        "deprecated_by_gate_113",
    ),
    (
        "in_memory_membership_directory.lookup",
        "organization_id",
        "dict key (no column, no rls)",
        "vocabulary_added_by_gate_113",
    ),
    (
        "in_memory_membership_directory.lookup",
        "organization_profile_id",
        "dict key (no column, no rls)",
        "correct_here_unchanged",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _csv(columns: tuple[str, ...], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _flag(value: Any) -> str:
    return str(bool(value)).lower()


def build_store_declaration() -> dict[str, Any]:
    """What the store is, anchored on values read from the services that own them."""
    from nativeforge.services.tenant_customer_org_binding_store_decision_service import (  # noqa: E501
        build_binding_store_decision,
    )
    from nativeforge.services.tenant_customer_org_binding_store_readiness_service import (  # noqa: E501
        build_binding_store_readiness,
    )
    from nativeforge.services.tenant_customer_org_binding_store_service import (
        FORBIDDEN_ANCHOR_NAMES,
        RLS_ANCHOR_COLUMN,
        STORABLE_BINDING_STATUSES,
        STORE_TABLE,
    )

    decision = build_binding_store_decision()
    readiness = build_binding_store_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "store_table": STORE_TABLE,
            "rls_anchor_column": RLS_ANCHOR_COLUMN,
            "rls_predicate": (
                "organization_id = current_setting('app.current_org_id', true)::uuid"
                " AND is_demo = current_setting('app.current_org_is_demo',"
                " true)::boolean"
            ),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "storable_binding_statuses": sorted(STORABLE_BINDING_STATUSES),
            "label_columns": ["tenant_id", "customer_org_id"],
            "label_columns_have_foreign_keys": False,
            "migration_defined": decision["migration_defined"],
            "migration_revision": decision["migration_revision"],
            "migration_applied": decision["migration_applied"],
            "store_writable": readiness["store_writable"],
            "operational_binding_storage_ready": readiness[
                "operational_binding_storage_ready"
            ],
            "demo_binding_storage_ready": readiness["demo_binding_storage_ready"],
            "blocked_reasons": readiness["blocked_reasons"],
            # Constants. Creating a table is not creating a capability.
            "rows_in_table": 0,
            "customer_bindings_stored": False,
            "customer_auth_live": False,
            "customer_persistence_live": False,
            "tenant_id_is_rls_authority": False,
            "customer_org_id_is_rls_authority": False,
            "organization_profile_id_is_rls_authority": False,
            "beta_onboarding_ready": False,
            "production_rollout_ready": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def render_store_matrix(fixture: dict[str, Any]) -> str:
    columns = (
        "case",
        "binding_status",
        "organization_id_shape",
        "rls_anchor",
        "is_demo",
        "storage_allowed",
        "write_allowed",
        "read_allowed",
        "operational",
        "human_review_required",
        "blocked_reasons",
    )
    rows = [
        [
            row["case"],
            row["binding_status"],
            row["organization_id_shape"],
            row["rls_anchor"] or "",
            _flag(row["is_demo"]),
            _flag(row["storage_allowed"]),
            _flag(row["write_allowed"]),
            _flag(row["read_allowed"]),
            _flag(row["operational"]),
            _flag(row["human_review_required"]),
            "; ".join(row["blocked_reasons"]),
        ]
        for row in fixture["rows"]
    ]
    return _csv(columns, rows)


def render_membership_wiring() -> str:
    columns = ("call_site", "parameter", "reaches", "gate_113_status")
    return _csv(columns, [list(row) for row in MEMBERSHIP_WIRING])


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Binding store readiness (Gate 113)")
    lines.append("")
    lines.append(
        "The table `nf_tenant_customer_org_bindings` exists as of migration "
        f"{declaration['migration_revision']}. **It is empty, no database has "
        "applied it, and no customer binding can be stored today.**"
    )
    lines.append("")
    lines.append("## What is still refused, and why")
    lines.append("")
    lines.append("```text")
    for reason in declaration["blocked_reasons"]:
        lines.append(reason)
    lines.append("```")
    lines.append("")
    lines.append(
        "None of these is addressed by a `CREATE TABLE`. A table under RLS "
        "holding zero rows is a container, not a capability."
    )
    lines.append("")
    lines.append("## The distinction this gate turns on")
    lines.append("")
    lines.append("```text")
    lines.append(
        f"migration_defined                  {_flag(declaration['migration_defined'])}"
        "   the revision file is in this repository"
    )
    lines.append(
        f"migration_applied                  {_flag(declaration['migration_applied'])}"
        "   a database has actually run it"
    )
    lines.append(
        "store_writable                     "
        f"{_flag(declaration['store_writable'])}   there is somewhere to write"
    )
    lines.append(
        "operational_binding_storage_ready  "
        f"{_flag(declaration['operational_binding_storage_ready'])}"
        "   a verified binding may be stored"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "These were a single hard-coded `migration_applied: False` before this "
        "gate. That constant was accidentally correct while no migration and no "
        "database existed, and would have become a lie the moment revision "
        f"{declaration['migration_revision']} landed."
    )
    lines.append("")
    lines.append("## The authority")
    lines.append("")
    lines.append("```text")
    lines.append(declaration["rls_predicate"])
    lines.append("```")
    lines.append("")
    lines.append(
        "`tenant_id` and `customer_org_id` are `text` columns carrying no "
        "foreign key. They are labels. A label with a foreign key becomes an "
        "identity space by accident."
    )
    lines.append("")
    lines.append("## Claims this gate does not make")
    lines.append("")
    lines.append("```text")
    for claim in (
        "customer_bindings_stored",
        "customer_auth_live",
        "customer_persistence_live",
        "tenant_id_is_rls_authority",
        "customer_org_id_is_rls_authority",
        "organization_profile_id_is_rls_authority",
        "beta_onboarding_ready",
        "production_rollout_ready",
    ):
        lines.append(f"{claim:44s} {_flag(declaration[claim])}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_store_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Output root only; inspection is by import."""
    from nativeforge.services.tenant_customer_org_binding_store_demo_fixture_service import (  # noqa: E501
        build_store_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_store_declaration()
    fixture = build_store_demo_fixture_set()

    written: dict[str, Any] = {}

    contract = out_dir / "tenant_customer_org_binding_store_contract.json"
    contract.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["contract"] = str(contract)

    matrix = out_dir / "tenant_customer_org_binding_store_matrix.csv"
    matrix.write_text(render_store_matrix(fixture), encoding="utf-8")
    written["store_matrix"] = str(matrix)

    fixtures = out_dir / "tenant_customer_org_binding_store_demo_fixtures.json"
    fixtures.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_fixtures"] = str(fixtures)

    wiring = out_dir / "membership_organization_id_wiring.csv"
    wiring.write_text(render_membership_wiring(), encoding="utf-8")
    written["membership_wiring"] = str(wiring)

    summary = out_dir / "tenant_customer_org_binding_store_readiness.md"
    summary.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["fixture"] = fixture
    return written


def store_artifact_invariant_failures(
    declaration: dict[str, Any],
    *,
    summary_text: str = "",
    matrix_text: str = "",
    wiring_text: str = "",
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for claim in (
        "customer_bindings_stored",
        "customer_auth_live",
        "customer_persistence_live",
        "tenant_id_is_rls_authority",
        "customer_org_id_is_rls_authority",
        "organization_profile_id_is_rls_authority",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "label_columns_have_foreign_keys",
        "fabricated",
        "live_fetch_performed",
    ):
        if declaration.get(claim) is not False:
            fails.append(f"store_artifact_claimed:{claim}")

    if declaration.get("rows_in_table") != 0:
        fails.append("store_artifact_reported_rows")

    if declaration.get("rls_anchor_column") != "organization_id":
        fails.append("store_artifact_anchored_on_a_label")

    # Every forbidden name must still be forbidden, individually.
    for name in ("tenant_id", "customer_org_id", "organization_profile_id"):
        if name not in (declaration.get("forbidden_anchor_names") or []):
            fails.append(f"forbidden_anchor_name_missing:{name}")

    # The summary must state the refusals rather than only the existence.
    if summary_text:
        for reason in declaration.get("blocked_reasons") or []:
            if reason not in summary_text:
                fails.append(f"summary_omits_blocked_reason:{reason}")
        if "It is empty" not in summary_text:
            fails.append("summary_does_not_say_the_table_is_empty")
        if declaration.get("rls_predicate") not in summary_text:
            fails.append("summary_omits_the_rls_predicate")

    # The matrix must show a refusal and an operational row, or it proves
    # nothing about the store's ability to distinguish them.
    if matrix_text:
        parsed = list(csv.reader(io.StringIO(matrix_text)))
        header, body = parsed[0], parsed[1:]
        if "operational" not in header:
            fails.append("matrix_missing_the_operational_column")
        else:
            operational = header.index("operational")
            storage = header.index("storage_allowed")
            reasons = header.index("blocked_reasons")
            if not any(row[operational] == "true" for row in body):
                fails.append("matrix_shows_no_operational_outcome")
            if not any(row[storage] == "false" for row in body):
                fails.append("matrix_shows_no_refusal")
            # A refused row with an empty reason column is a refusal that does
            # not say why, which is the thing the matrix exists to prevent.
            for row in body:
                if row[storage] == "false" and not row[reasons].strip():
                    fails.append(f"matrix_refusal_without_a_reason:{row[0]}")

    # The wiring table must name organization_id as what the postgres lookup takes.
    if wiring_text:
        if "lookup_membership,organization_id," not in wiring_text:
            fails.append("wiring_does_not_show_the_renamed_lookup")
        if "organization_profile_id" not in wiring_text:
            fails.append("wiring_omits_the_deprecated_parameter")

    return fails
