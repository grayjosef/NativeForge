"""Customer pilot auth scaffolding contracts (Campaign Block 24)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_customer_access_boundary_contract_v1"

AUTH_MODES = frozenset(
    {
        "not_supported",
        "demo_operator_view",
        "fixture_scoped",
        "internal_preview",
        "external_pilot_not_enabled",
        "production_not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_customer_access_boundary_id(org_id: str, cohort_id: str) -> str:
    raw = f"cab::{org_id}::{cohort_id}".encode()
    return f"cab_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_customer_access_boundary_contract(
    *,
    organization_profile_id: str,
    pilot_cohort_id: str,
    allowed_routes: list[str] | None = None,
    allowed_surfaces: list[str] | None = None,
    disallowed_surfaces: list[str] | None = None,
    data_scope: str = "organization_only",
    auth_mode: str = "fixture_scoped",
    allowed_package_ids: list[str] | None = None,
    allowed_evidence_ids: list[str] | None = None,
    allowed_feedback_context_ids: list[str] | None = None,
) -> dict[str, Any]:
    mode = auth_mode if auth_mode in AUTH_MODES else "not_supported"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "customer_access_boundary_id": make_customer_access_boundary_id(
                organization_profile_id, pilot_cohort_id
            ),
            "organization_profile_id": organization_profile_id,
            "pilot_cohort_id": pilot_cohort_id,
            "allowed_routes": list(allowed_routes or ["/?view=sc_customer_demo"]),
            "allowed_surfaces": list(
                allowed_surfaces
                or [
                    "package_readiness",
                    "evidence_intake",
                    "forms_attachments_map",
                    "package_export_preview",
                ]
            ),
            "disallowed_surfaces": list(
                disallowed_surfaces
                or [
                    "collaboration_matching",
                    "production_admin",
                    "cross_org_operator_override",
                ]
            ),
            "data_scope": data_scope,
            "auth_mode": mode,
            "allowed_package_ids": list(allowed_package_ids or []),
            "allowed_evidence_ids": list(allowed_evidence_ids or []),
            "allowed_feedback_context_ids": list(allowed_feedback_context_ids or []),
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "rbac_enforced_claimed": False,
            "production_multi_tenant_claimed": False,
            "customer_data_isolation_claimed": False,
            "operator_review_required": True,
            "collaboration_enabled": False,
            "upload_persistence_claimed": False,
            "final_export_claimed": False,
            "submission_ready_claimed": False,
            "operator_override_supported": False,
            "live_ingest_claimed": False,
        }
    )


def customer_access_boundary_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "rbac_enforced_claimed",
        "production_multi_tenant_claimed",
        "customer_data_isolation_claimed",
        "collaboration_enabled",
        "upload_persistence_claimed",
        "final_export_claimed",
        "submission_ready_claimed",
        "operator_override_supported",
        "live_ingest_claimed",
    ):
        if contract.get(key) is True:
            fails.append(key)
    if contract.get("auth_mode") not in AUTH_MODES:
        fails.append("bad_auth_mode")
    if contract.get("operator_review_required") is not True:
        fails.append("operator_review_not_required")
    return fails


def assert_no_cross_org_access(
    boundary: dict[str, Any],
    *,
    other_org_id: str,
    other_package_ids: list[str] | None = None,
    other_evidence_ids: list[str] | None = None,
    other_feedback_ids: list[str] | None = None,
) -> list[str]:
    """Return failures if foreign org resources appear in this boundary."""
    fails: list[str] = []
    if boundary.get("organization_profile_id") == other_org_id:
        return fails
    for pid in other_package_ids or []:
        if pid and pid in (boundary.get("allowed_package_ids") or []):
            fails.append(f"package_leak:{pid}")
    for eid in other_evidence_ids or []:
        if eid and eid in (boundary.get("allowed_evidence_ids") or []):
            fails.append(f"evidence_leak:{eid}")
    for fid in other_feedback_ids or []:
        if fid and fid in (boundary.get("allowed_feedback_context_ids") or []):
            fails.append(f"feedback_leak:{fid}")
    return fails
