"""Customer auth boundary artifacts (Gate 111G).

Five committed files recording who may act, who may verify a binding, and what
may never set the RLS context.

## The matrices carry the weight

A contract can say "a demo principal may not verify a production binding". The
binder matrix shows it — nine principals against six operations, in both a
production and a demo target context, with `binding_authorized` scannable in one
column.

## Output root is not inspection root

`repo_root` chooses where files land. It never influences what is measured; the
readiness inputs resolve by import. Gate 101 found writers conflating the two.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_boundary_artifact_v1"

ARTIFACT_DIR = "artifacts/customer_auth_boundary"

DECLARATION_KEYS: tuple[str, ...] = (
    "customer_auth_contract_available",
    "customer_auth_live",
    "login_live",
    "verified_binder_authorization_available",
    "rls_context_claim_guard_available",
    "binding_store_built",
    "verified_operational_binding",
    "operational_awarded_tracking_ready",
    "operational_digest_ready",
    "beta_onboarding_ready",
)

BINDER_COLUMNS: tuple[str, ...] = (
    "target_binding_status",
    "case",
    "auth_status",
    "verifier_role",
    "binding_operation",
    "binding_authorized",
    "org_membership_verified",
    "cross_tenant_risk",
)

CLAIM_COLUMNS: tuple[str, ...] = (
    "claimed_identity_name",
    "claimed_identity_shape",
    "claim_source",
    "claim_verified",
    "rls_context_allowed",
    "set_current_org_allowed",
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


def build_auth_boundary_declaration() -> dict[str, Any]:
    """What the auth lane claims. Login-live is read from the promotion gate."""
    from nativeforge.services import (
        tenant_customer_org_binding_store_decision_service as store_decision,
    )
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
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

    # Detected, not declared: the existing promotion gate owns this answer.
    promotion = evaluate_login_live_promotion()
    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()
    decision = store_decision.build_binding_store_decision()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "customer_auth_contract_available": True,
            "verified_binder_authorization_available": True,
            "rls_context_claim_guard_available": True,
            "customer_auth_live": bool(promotion.get("production_auth_claimed")),
            "login_live": bool(promotion.get("login_live_claimed")),
            "login_promotion_gates_missing": list(
                promotion.get("missing_gates") or []
            ),
            "controlled_pilot_auth_ready": bool(
                promotion.get("controlled_pilot_auth_ready")
            ),
            "binding_store_built": bool(decision.get("migration_applied")),
            "binding_store_recommended": decision.get("recommended_store"),
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
            "cloudflare_access_is_app_auth": False,
            "demo_auth_is_production_auth": False,
            "tenant_id_can_set_current_org_id": False,
            "customer_org_id_can_set_current_org_id": False,
            "identity_provider_contacted": False,
            "sessions_created": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "live_fetch_performed": False,
            "fabricated": False,
        }
    )


def render_binder_matrix(fixture: dict[str, Any]) -> str:
    case_by_id = {p["principal_id"]: p.get("case") for p in fixture["principals"]}
    rows = []
    for key in ("production_binder_matrix", "demo_binder_matrix"):
        matrix = fixture.get(key) or {}
        target = matrix.get("target_binding_status") or "production"
        for row in matrix.get("rows") or []:
            rows.append(
                [
                    target,
                    case_by_id.get(row.get("principal_id"), "unknown"),
                    row.get("auth_status"),
                    row.get("verifier_role") or "",
                    row.get("binding_operation"),
                    _flag(row.get("binding_authorized")),
                    _flag(row.get("org_membership_verified")),
                    _flag(row.get("cross_tenant_risk")),
                ]
            )
    return _csv(BINDER_COLUMNS, rows)


def render_claim_matrix(fixture: dict[str, Any]) -> str:
    matrix = fixture.get("claim_guard_matrix") or {}
    rows = []
    for row in matrix.get("rows") or []:
        rows.append(
            [
                row.get("claimed_identity_name"),
                row.get("claimed_identity_shape"),
                row.get("claim_source"),
                _flag(row.get("claim_verified")),
                _flag(row.get("rls_context_allowed")),
                _flag(row.get("set_current_org_allowed")),
                _flag(row.get("cross_tenant_risk")),
            ]
        )
    return _csv(CLAIM_COLUMNS, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Customer auth boundary")
    lines.append("")
    lines.append(
        "The contracts that decide who may act, who may verify a binding, and "
        "what may set `app.current_org_id`. None of them logs anybody in."
    )
    lines.append("")
    lines.append("## What exists")
    lines.append("")
    lines.append("```text")
    for key in (
        "customer_auth_contract_available",
        "verified_binder_authorization_available",
        "rls_context_claim_guard_available",
        "binding_store_recommended",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## What is not live")
    lines.append("")
    lines.append(
        "Read from the existing login promotion gate rather than asserted here."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "customer_auth_live",
        "login_live",
        "controlled_pilot_auth_ready",
        "binding_store_built",
        "verified_operational_binding",
        "customer_persistence_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("Login promotion gates still missing:")
    lines.append("")
    lines.append("```text")
    for gate in declaration.get("login_promotion_gates_missing") or ["none"]:
        lines.append(str(gate))
    lines.append("```")
    lines.append("")
    lines.append("## What the boundary refuses")
    lines.append("")
    lines.append("```text")
    for key in (
        "cloudflare_access_is_app_auth",
        "demo_auth_is_production_auth",
        "tenant_id_can_set_current_org_id",
        "customer_org_id_can_set_current_org_id",
        "identity_provider_contacted",
        "sessions_created",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Cloudflare Access controls who reaches the host; it establishes no "
        "organization and sets no RLS context. A demo principal may verify a "
        "demo binding and nothing else. An authenticated person is not a "
        "verified member of any organization until somebody establishes one."
    )
    lines.append("")
    return "\n".join(lines)


def write_auth_boundary_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Output root only; inspection is by import."""
    from nativeforge.services.customer_auth_demo_fixture_service import (
        build_demo_auth_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_auth_boundary_declaration()
    fixture = build_demo_auth_fixture_set()

    written: dict[str, Any] = {}

    contract = out_dir / "customer_auth_principal_contract.json"
    contract.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["principal_contract"] = str(contract)

    binder = out_dir / "verified_binder_authorization_matrix.csv"
    binder.write_text(render_binder_matrix(fixture), encoding="utf-8")
    written["binder_matrix"] = str(binder)

    claims = out_dir / "rls_context_claim_guard_matrix.csv"
    claims.write_text(render_claim_matrix(fixture), encoding="utf-8")
    written["claim_matrix"] = str(claims)

    principals = out_dir / "customer_auth_demo_principals.json"
    principals.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_principals"] = str(principals)

    summary = out_dir / "customer_auth_readiness_summary.md"
    summary.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["fixture"] = fixture
    return written


def auth_artifact_invariant_failures(declaration: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for key in DECLARATION_KEYS:
        if key not in declaration:
            fails.append(f"declaration_missing_key:{key}")

    for constant in (
        "cloudflare_access_is_app_auth",
        "demo_auth_is_production_auth",
        "tenant_id_can_set_current_org_id",
        "customer_org_id_can_set_current_org_id",
        "identity_provider_contacted",
        "sessions_created",
        "source_monitoring_live",
        "source_coverage_claimed",
        "live_fetch_performed",
        "fabricated",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"auth_artifact_claimed:{constant}")

    # Nothing operational may be declared ready or live.
    for key in (
        "customer_auth_live",
        "login_live",
        "binding_store_built",
        "verified_operational_binding",
        "customer_persistence_live",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
    ):
        if declaration.get(key) is not False:
            fails.append(f"auth_artifact_claimed_operational:{key}")

    # The contracts must be present for the claims about them to mean anything.
    if declaration.get("verified_binder_authorization_available") and not (
        declaration.get("customer_auth_contract_available")
    ):
        fails.append("binder_authorization_claimed_without_the_principal_contract")

    return fails
