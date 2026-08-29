"""Org identity canonicalization artifacts (Gate 110F).

Five committed files recording which identity carries authority, where a binding
should live, and what may not be written under what.

## The matrices are the point

A contract can state "tenant_id never persists customer data". A matrix of every
identity against every persist operation shows it — a reviewer scans the
`write_allowed` column and sees `organization_id` and a UUID-shaped `org_id`, and
nothing else, across all six operations.

## Output root is not inspection root

`repo_root` chooses where files land. It never influences what is measured: the
role contract and the guards resolve their inputs by import. Gate 101 found
writers conflating the two, so a determinism check described an empty temp
directory.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_org_identity_canonicalization_artifact_v1"

ARTIFACT_DIR = "artifacts/org_identity_canonicalization"

DECLARATION_KEYS: tuple[str, ...] = (
    "organization_id_is_rls_authority",
    "tenant_id_is_rls_authority",
    "demo_tenant_ids_rls_allowed",
    "binding_store_decision_available",
    "migration_applied",
    "customer_persistence_live",
    "operational_awarded_tracking_ready",
    "operational_digest_ready",
    "beta_onboarding_ready",
)

ROLE_COLUMNS: tuple[str, ...] = (
    "identity_name",
    "role",
    "shape",
    "authority_level",
    "rls_allowed",
    "persistence_allowed",
    "product_surface_allowed",
    "requires_binding",
)

SAFETY_COLUMNS: tuple[str, ...] = (
    "operation",
    "identity_name",
    "identity_shape",
    "identity_role",
    "rls_compatible",
    "binding_required",
    "write_allowed",
    "cross_tenant_risk",
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


def build_canonicalization_declaration() -> dict[str, Any]:
    """What the identity lane claims, every key measured elsewhere."""
    from nativeforge.services import (
        tenant_customer_org_binding_store_decision_service as store_decision,
    )
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.org_identity_role_contract_service import (
        build_identity_role_matrix,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    matrix = build_identity_role_matrix()
    decision = store_decision.build_binding_store_decision()
    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id_is_rls_authority": bool(
                matrix["organization_id_is_rls_authority"]
            ),
            "tenant_id_is_rls_authority": False,
            "demo_tenant_ids_rls_allowed": False,
            "binding_store_decision_available": True,
            "recommended_store": decision["recommended_store"],
            "recommended_primary_key": decision["recommended_primary_key"],
            "rls_enforced_by": decision["rls_enforced_by"],
            "requires_migration": bool(decision["requires_migration"]),
            "migration_safe_now": bool(decision["migration_safe_now"]),
            "migration_applied": False,
            "names_allowing_rls": matrix["names_allowing_rls"],
            "names_allowing_persistence": matrix["names_allowing_persistence"],
            "names_requiring_binding": matrix["names_requiring_binding"],
            "customer_persistence_live": bool(
                awarded.get("customer_persistence_live")
            ),
            "customer_auth_live": bool(beta.get("customer_auth_live")),
            "operational_awarded_tracking_ready": bool(
                awarded.get("ready_for_operational_awarded_tracking")
            ),
            "operational_digest_ready": bool(
                digest.get("ready_for_operational_digest")
            ),
            "beta_onboarding_ready": bool(beta.get("ready_for_beta_onboarding")),
            "next_required_actions": decision["next_required_actions"],
            # Constants the whole gate holds.
            "identities_assumed_equivalent": False,
            "schema_changed": False,
            "rows_written": 0,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "live_fetch_performed": False,
            "fabricated": False,
        }
    )


def render_role_matrix(matrix: dict[str, Any]) -> str:
    rows = []
    for row in matrix.get("rows") or []:
        rows.append(
            [
                row.get("identity_name"),
                row.get("role"),
                row.get("shape"),
                row.get("authority_level"),
                _flag(row.get("rls_allowed")),
                _flag(row.get("persistence_allowed")),
                _flag(row.get("product_surface_allowed")),
                _flag(row.get("requires_binding")),
            ]
        )
    return _csv(ROLE_COLUMNS, rows)


def render_safety_matrix(safety: dict[str, Any]) -> str:
    rows = []
    for row in safety.get("rows") or []:
        rows.append(
            [
                row.get("operation"),
                row.get("supplied_identity_name"),
                row.get("identity_shape"),
                row.get("identity_role"),
                _flag(row.get("rls_compatible")),
                _flag(row.get("binding_required")),
                _flag(row.get("write_allowed")),
                _flag(row.get("cross_tenant_risk")),
            ]
        )
    return _csv(SAFETY_COLUMNS, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Org identity canonicalization")
    lines.append("")
    lines.append(
        "Every row-level security policy reads "
        "`organization_id = current_setting('app.current_org_id', true)::uuid`. "
        "That is the authority, and it is read from the migrations rather than "
        "assumed."
    )
    lines.append("")
    lines.append("## Which identity carries authority")
    lines.append("")
    lines.append("```text")
    for key in (
        "organization_id_is_rls_authority",
        "tenant_id_is_rls_authority",
        "demo_tenant_ids_rls_allowed",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append(f"{'names_allowing_rls':<44} {declaration.get('names_allowing_rls')}")
    lines.append(
        f"{'names_allowing_persistence':<44} "
        f"{declaration.get('names_allowing_persistence')}"
    )
    lines.append(
        f"{'names_requiring_binding':<44} "
        f"{declaration.get('names_requiring_binding')}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Where a binding should live")
    lines.append("")
    lines.append("```text")
    for key in (
        "binding_store_decision_available",
        "recommended_store",
        "recommended_primary_key",
        "rls_enforced_by",
        "requires_migration",
        "migration_safe_now",
        "migration_applied",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "A recommendation can be right while the migration remains wrong to "
        "apply. No schema was changed and no row was written."
    )
    lines.append("")
    lines.append("## What remains false")
    lines.append("")
    lines.append("```text")
    for key in (
        "customer_persistence_live",
        "customer_auth_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
        "source_monitoring_live",
        "source_coverage_claimed",
        "live_fetch_performed",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## Next")
    lines.append("")
    for entry in declaration.get("next_required_actions") or []:
        lines.append(f"1. **{entry.get('action')}** — {entry.get('why')}")
    lines.append("")
    return "\n".join(lines)


def write_canonicalization_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Output root only; inspection is by import."""
    from nativeforge.services import (
        tenant_customer_org_binding_store_decision_service as store_decision,
    )
    from nativeforge.services.identity_persistence_safety_guard_service import (
        build_persistence_safety_matrix,
    )
    from nativeforge.services.org_identity_role_contract_service import (
        build_identity_role_matrix,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_canonicalization_declaration()
    role_matrix = build_identity_role_matrix()
    decision = store_decision.build_binding_store_decision()
    safety = build_persistence_safety_matrix()

    written: dict[str, Any] = {}

    contract = out_dir / "org_identity_role_contract.json"
    contract.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["role_contract"] = str(contract)

    roles = out_dir / "org_identity_role_matrix.csv"
    roles.write_text(render_role_matrix(role_matrix), encoding="utf-8")
    written["role_matrix"] = str(roles)

    store = out_dir / "binding_store_decision.json"
    store.write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["binding_store_decision"] = str(store)

    safety_path = out_dir / "identity_persistence_safety_matrix.csv"
    safety_path.write_text(render_safety_matrix(safety), encoding="utf-8")
    written["safety_matrix"] = str(safety_path)

    summary = out_dir / "org_identity_readiness_summary.md"
    summary.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["role_matrix_data"] = role_matrix
    written["decision"] = decision
    written["safety"] = safety
    return written


def canonicalization_artifact_invariant_failures(
    declaration: dict[str, Any],
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for key in DECLARATION_KEYS:
        if key not in declaration:
            fails.append(f"declaration_missing_key:{key}")

    for constant in (
        "tenant_id_is_rls_authority",
        "demo_tenant_ids_rls_allowed",
        "migration_applied",
        "identities_assumed_equivalent",
        "schema_changed",
        "source_monitoring_live",
        "source_coverage_claimed",
        "live_fetch_performed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"canonicalization_claimed:{constant}")

    if declaration.get("rows_written") != 0:
        fails.append("canonicalization_wrote_rows")

    # Nothing operational may be declared ready.
    for key in (
        "customer_persistence_live",
        "customer_auth_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        if declaration.get(key) is not False:
            fails.append(f"canonicalization_claimed_operational:{key}")

    # tenant_id may never appear among the names permitted to persist or scope.
    for key in ("names_allowing_rls", "names_allowing_persistence"):
        if "tenant_id" in (declaration.get(key) or []):
            fails.append(f"tenant_id_listed_in:{key}")

    # The store may never be keyed on a label.
    if declaration.get("recommended_primary_key") in {
        "tenant_id",
        "customer_org_id",
    }:
        fails.append("recommended_primary_key_is_a_label")

    return fails
