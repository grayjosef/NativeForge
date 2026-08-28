"""Tenant / customer org identity artifacts (Gate 109G).

Five committed files recording the binding contract and, more usefully, the
whole decision surface of the resolution guard.

## The guard matrix is the point

A contract document can say "unbound blocks operational writes". A matrix of
every binding status against every operation shows it, row by row, and a
reviewer can scan the `write_allowed` column and see that it is false everywhere
outside a demo context.

## Output root is not inspection root

`repo_root` chooses where files land. It never influences what is measured -
readiness resolves modules through the import system. Gate 101 found writers
conflating the two, so a determinism check described an empty temp directory.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_customer_org_identity_artifact_v1"

ARTIFACT_DIR = "artifacts/tenant_customer_org_identity_binding"

DECLARATION_KEYS: tuple[str, ...] = (
    "identity_binding_contract_available",
    "demo_fixture_bindings_available",
    "verified_operational_binding_available",
    "customer_persistence_live",
    "customer_auth_live",
    "operational_awarded_tracking_ready",
    "operational_digest_ready",
    "beta_onboarding_ready",
)

IDENTITY_COLUMNS: tuple[str, ...] = (
    "case",
    "tenant_id",
    "customer_org_id",
    "tenant_id_shape",
    "binding_status",
    "binding_source",
    "binding_confidence",
    "is_production_verified",
    "human_review_required",
)

GUARD_COLUMNS: tuple[str, ...] = (
    "demo_context",
    "binding_status",
    "operation",
    "resolution_allowed",
    "read_allowed",
    "write_allowed",
    "cross_tenant_risk",
    "human_review_required",
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


def build_identity_declaration() -> dict[str, Any]:
    """What the identity lane claims, every key measured elsewhere."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )
    from nativeforge.services.tenant_nofo_digest_readiness_service import (
        build_digest_readiness,
    )

    awarded = build_awarded_requirements_readiness()
    digest = build_digest_readiness()
    beta = build_tenant_beta_readiness()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_binding_contract_available": True,
            "demo_fixture_bindings_available": True,
            "verified_operational_binding_available": bool(
                awarded.get("verified_operational_identity_binding")
            ),
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
            "awarded_demo_contract_ready": bool(
                awarded.get("ready_for_demo_contract")
            ),
            "digest_demo_preview_ready": bool(digest.get("ready_for_demo_preview")),
            "beta_demo_ready": bool(beta.get("ready_for_demo")),
            # Constants the whole gate holds.
            "identities_assumed_equivalent": False,
            "tenant_id_derived_from_customer_org_id": False,
            "customer_org_id_derived_from_tenant_id": False,
            "bindings_persisted": False,
            "source_monitoring_live": False,
            "source_coverage_claimed": False,
            "live_source_collection_available": False,
            "live_fetch_performed": False,
        }
    )


def render_identity_matrix(fixture: dict[str, Any]) -> str:
    rows = []
    for binding in fixture.get("bindings") or []:
        rows.append(
            [
                binding.get("case"),
                binding.get("tenant_id") or "",
                binding.get("customer_org_id") or "",
                binding.get("tenant_id_shape"),
                binding.get("binding_status"),
                binding.get("binding_source"),
                binding.get("binding_confidence"),
                _flag(binding.get("is_production_verified")),
                _flag(binding.get("human_review_required")),
            ]
        )
    return _csv(IDENTITY_COLUMNS, rows)


def render_guard_matrix(fixture: dict[str, Any]) -> str:
    rows = []
    for key in ("demo_context_matrix", "operational_context_matrix"):
        matrix = fixture.get(key) or {}
        for row in matrix.get("rows") or []:
            rows.append(
                [
                    _flag(matrix.get("demo_context")),
                    row.get("binding_status"),
                    row.get("operation"),
                    _flag(row.get("resolution_allowed")),
                    _flag(row.get("read_allowed")),
                    _flag(row.get("write_allowed")),
                    _flag(row.get("cross_tenant_risk")),
                    _flag(row.get("human_review_required")),
                ]
            )
    return _csv(GUARD_COLUMNS, rows)


def render_readiness_summary(declaration: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Tenant / customer org identity binding")
    lines.append("")
    lines.append(
        "`tenant_id` and `customer_org_id` are not automatically equivalent. A "
        "relationship between them exists only where somebody recorded one and "
        "it was checked."
    )
    lines.append("")
    lines.append("## What exists")
    lines.append("")
    lines.append("```text")
    for key in (
        "identity_binding_contract_available",
        "demo_fixture_bindings_available",
        "awarded_demo_contract_ready",
        "digest_demo_preview_ready",
        "beta_demo_ready",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## What does not")
    lines.append("")
    lines.append(
        "A demo binding is not production verification. Nothing below can be "
        "reached without a verified, non-demo binding."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "verified_operational_binding_available",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
        "customer_auth_live",
        "customer_persistence_live",
        "live_source_collection_available",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append("## Nothing is derived")
    lines.append("")
    lines.append("```text")
    for key in (
        "identities_assumed_equivalent",
        "tenant_id_derived_from_customer_org_id",
        "customer_org_id_derived_from_tenant_id",
        "bindings_persisted",
        "live_fetch_performed",
    ):
        lines.append(f"{key:<44} {declaration.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Matching strings do not create a binding, and neither do matching "
        "names. One value used for both identity spaces is a conflict, not a "
        "shortcut."
    )
    lines.append("")
    return "\n".join(lines)


def write_identity_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write all five artifacts. Output root only; inspection is by import."""
    from nativeforge.services.tenant_customer_org_demo_identity_fixture_service import (
        build_demo_identity_fixture_set,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    declaration = build_identity_declaration()
    fixture = build_demo_identity_fixture_set()

    written: dict[str, Any] = {}

    contract = out_dir / "tenant_customer_org_identity_binding_contract.json"
    contract.write_text(
        json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["contract"] = str(contract)

    identity_matrix = out_dir / "tenant_customer_org_identity_matrix.csv"
    identity_matrix.write_text(render_identity_matrix(fixture), encoding="utf-8")
    written["identity_matrix"] = str(identity_matrix)

    guard_matrix = out_dir / "tenant_customer_org_resolution_guard_matrix.csv"
    guard_matrix.write_text(render_guard_matrix(fixture), encoding="utf-8")
    written["guard_matrix"] = str(guard_matrix)

    bindings = out_dir / "tenant_customer_org_demo_bindings.json"
    bindings.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written["demo_bindings"] = str(bindings)

    summary = out_dir / "tenant_customer_org_readiness_summary.md"
    summary.write_text(render_readiness_summary(declaration), encoding="utf-8")
    written["readiness_summary"] = str(summary)

    written["declaration"] = declaration
    written["fixture"] = fixture
    return written


def identity_artifact_invariant_failures(declaration: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if declaration.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for key in DECLARATION_KEYS:
        if key not in declaration:
            fails.append(f"declaration_missing_key:{key}")

    for constant in (
        "identities_assumed_equivalent",
        "tenant_id_derived_from_customer_org_id",
        "customer_org_id_derived_from_tenant_id",
        "bindings_persisted",
        "source_monitoring_live",
        "source_coverage_claimed",
        "live_source_collection_available",
        "live_fetch_performed",
    ):
        if declaration.get(constant) is not False:
            fails.append(f"identity_artifact_claimed:{constant}")

    # Nothing operational may be declared ready.
    for key in (
        "verified_operational_binding_available",
        "operational_awarded_tracking_ready",
        "operational_digest_ready",
        "beta_onboarding_ready",
        "customer_auth_live",
        "customer_persistence_live",
    ):
        if declaration.get(key) is not False:
            fails.append(f"identity_artifact_claimed_operational:{key}")

    # The contract itself must be present for the demo claims to mean anything.
    if declaration.get("demo_fixture_bindings_available") and not declaration.get(
        "identity_binding_contract_available"
    ):
        fails.append("demo_bindings_claimed_without_the_contract")

    return fails
