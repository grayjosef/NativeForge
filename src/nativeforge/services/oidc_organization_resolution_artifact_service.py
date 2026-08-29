"""OIDC organization resolution artifacts (Gate 112H).

Six committed files recording how a claim becomes an `organization_id`, when it
does not, and what still stands between the dev header and production.

## Output root is not inspection root

`repo_root` chooses where files land. It never influences what is measured; the
readiness and containment inputs resolve by import and by reading the unit file.
Gate 101 found writers conflating the two.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_oidc_organization_resolution_artifact_v1"

ARTIFACT_DIR = "artifacts/oidc_organization_id_resolution"

DECLARATION_KEYS: tuple[str, ...] = (
    "oidc_organization_id_resolution_contract_available",
    "organization_profile_id_is_rls_authority",
    "organization_id_required_for_rls",
    "customer_auth_live",
    "login_live",
    "dev_header_production_safe",
    "binding_store_built",
    "verified_operational_binding",
    "operational_awarded_tracking_ready",
    "operational_digest_ready",
    "beta_onboarding_ready",
)

RESOLUTION_COLUMNS: tuple[str, ...] = (
    "case",
    "auth_source",
    "claims_verified",
    "organization_claim_value",
    "organization_profile_id",
    "organization_id_shape",
    "resolution_status",
    "resolved_organization_id",
    "membership_verified",
    "rls_context_allowed",
)

MEMBERSHIP_COLUMNS: tuple[str, ...] = (
    "principal_id",
    "organization_id",
    "organization_id_shape",
    "membership_status",
    "membership_source",
    "membership_verified",
    "can_set_rls_context",
    "can_verify_binding",
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


def build_resolution_declaration() -> dict[str, Any]:
    """What the resolution lane claims. Live facts read from their owners."""
    from nativeforge.services import (
        tenant_customer_org_binding_store_decision_service as store_decision,
    )
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.dev_org_header_containment_service import (
        build_dev_header_containment,
    )
    from nativeforge.services.login_live_promotion_gate_service import (
        evaluate_login_live_promotion,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    promotion = evaluate_login_live_promotion()
    containment = build_dev_header_containment()
    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()
    decision = store_decision.build_binding_store_decision()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "oidc_organization_id_resolution_contract_available": True,
            "membership_verification_contract_available": True,
            "dev_header_containment_contract_available": True,
            "organization_profile_id_is_rls_authority": False,
            "organization_id_required_for_rls": True,
            "customer_auth_live": bool(promotion.get("production_auth_claimed")),
            "login_live": bool(promotion.get("login_live_claimed")),
            "login_promotion_gates_missing": list(
                promotion.get("missing_gates") or []
            ),
            "dev_header_production_safe": bool(containment.get("production_safe")),
            "dev_header_contained_by_deployment_posture": bool(
                containment.get("contained_by_deployment_posture")
            ),
            "binding_store_built": bool(decision.get("migration_applied")),
            "verified_operational_binding": bool(
                awarded.get("verified_operational_identity_binding")
            ),
            "operational_awarded_tracking_ready": bool(
                awarded.get("ready_for_operational_awarded_tracking")
            ),
            "operational_digest_ready": bool(
                digest.get("ready_for_operational_digest")
            ),
            "beta_onboarding_ready": bool(beta.get("ready_for_beta_onboarding")),
            "customer_persistence_live": bool(
                awarded.get("customer_persistence_live")
            ),
            # Constants the whole gate holds.
            "migration_applied": False,
            "schema_changed": False,
            "identity_provider_contacted": False,
            "current_org_id_set": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "live_fetch_performed": False,
            "fabricated": False,
        }
    )


def render_resolution_matrix(fixture: dict[str, Any]) -> str:
    rows = []
    for row in fixture.get("resolution_rows") or []:
        rows.append(
            [
                row.get("case"),
                row.get("auth_source"),
                _flag(row.get("claims_verified")),
                row.get("organization_claim_value") or "",
                row.get("organization_profile_id") or "",
                row.get("organization_id_shape"),
                row.get("resolution_status"),
                row.get("resolved_organization_id") or "",
                _flag(row.get("membership_verified")),
                _flag(row.get("rls_context_allowed")),
            ]
        )
    return _csv(RESOLUTION_COLUMNS, rows)


def render_membership_matrix(fixture: dict[str, Any]) -> str:
    matrix = fixture.get("membership_matrix") or {}
    rows = []
    for row in matrix.get("rows") or []:
        rows.append(
            [
                row.get("principal_id") or "",
                row.get("organization_id") or "",
                row.get("organization_id_shape"),
                row.get("membership_status"),
                row.get("membership_source"),
                _flag(row.get("membership_verified")),
                _flag(row.get("can_set_rls_context")),
                _flag(row.get("can_verify_binding")),
            ]
        )
    return _csv(MEMBERSHIP_COLUMNS, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# OIDC organization_id resolution")
    lines.append("")
    lines.append(
        "Every row-level security policy reads "
        "`organization_id = current_setting('app.current_org_id', true)::uuid`. "
        "A claim reaches that boundary only by resolving to an organization_id "
        "and only alongside verified membership."
    )
    lines.append("")
    lines.append("## What exists")
    lines.append("")
    lines.append("```text")
    for key in (
        "oidc_organization_id_resolution_contract_available",
        "membership_verification_contract_available",
        "dev_header_containment_contract_available",
        "organization_id_required_for_rls",
    ):
        lines.append(f"{key:<52} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## What is not live")
    lines.append("")
    lines.append(
        "Read from the login promotion gate and the containment service rather "
        "than asserted here."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "customer_auth_live",
        "login_live",
        "dev_header_production_safe",
        "binding_store_built",
        "verified_operational_binding",
        "customer_persistence_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        lines.append(f"{key:<52} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("Login promotion gates still missing:")
    lines.append("")
    lines.append("```text")
    for gate in declaration.get("login_promotion_gates_missing") or ["none"]:
        lines.append(str(gate))
    lines.append("```")
    lines.append("")
    lines.append("## What the contract refuses")
    lines.append("")
    lines.append("```text")
    for key in (
        "organization_profile_id_is_rls_authority",
        "migration_applied",
        "schema_changed",
        "identity_provider_contacted",
        "current_org_id_set",
        "live_fetch_performed",
    ):
        lines.append(f"{key:<52} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "An organization_profile_id is carried as evidence and never promoted. "
        "The dev header is contained by deployment posture today and is still "
        "not production-safe, because an unauthenticated header can set the org "
        "context regardless of how well the deployment happens to be closed."
    )
    lines.append("")
    return "\n".join(lines)


def write_resolution_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all six artifacts. Output root only; inspection is by import."""
    from nativeforge.services.dev_org_header_containment_service import (
        build_dev_header_containment,
    )
    from nativeforge.services.oidc_organization_resolution_demo_fixture_service import (
        build_resolution_demo_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_resolution_declaration()
    fixture = build_resolution_demo_fixture_set()
    containment = build_dev_header_containment()

    written: dict[str, Any] = {}

    contract = out_dir / "oidc_organization_id_resolution_contract.json"
    contract.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["contract"] = str(contract)

    resolution = out_dir / "oidc_organization_id_resolution_matrix.csv"
    resolution.write_text(render_resolution_matrix(fixture), encoding="utf-8")
    written["resolution_matrix"] = str(resolution)

    membership = out_dir / "customer_org_membership_verification_matrix.csv"
    membership.write_text(render_membership_matrix(fixture), encoding="utf-8")
    written["membership_matrix"] = str(membership)

    header = out_dir / "dev_org_header_containment_summary.json"
    header.write_text(
        json.dumps(containment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["dev_header_summary"] = str(header)

    fixtures = out_dir / "oidc_organization_resolution_demo_fixtures.json"
    fixtures.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_fixtures"] = str(fixtures)

    summary = out_dir / "oidc_organization_id_resolution_readiness_summary.md"
    summary.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["fixture"] = fixture
    written["containment"] = containment
    return written


def resolution_artifact_invariant_failures(
    declaration: dict[str, Any],
) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for key in DECLARATION_KEYS:
        if key not in declaration:
            fails.append(f"declaration_missing_key:{key}")

    for constant in (
        "organization_profile_id_is_rls_authority",
        "migration_applied",
        "schema_changed",
        "identity_provider_contacted",
        "current_org_id_set",
        "source_monitoring_live",
        "source_coverage_claimed",
        "live_fetch_performed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"resolution_artifact_claimed:{constant}")

    if declaration.get("organization_id_required_for_rls") is not True:
        fails.append("organization_id_no_longer_required_for_rls")

    # Nothing operational or live may be declared.
    for key in (
        "customer_auth_live",
        "login_live",
        "dev_header_production_safe",
        "binding_store_built",
        "verified_operational_binding",
        "customer_persistence_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        if declaration.get(key) is not False:
            fails.append(f"resolution_artifact_claimed_operational:{key}")

    return fails
