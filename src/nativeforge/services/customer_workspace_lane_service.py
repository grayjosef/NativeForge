"""Workspace lane resolution: authentication ≠ affiliation ≠ entitlement.

Canonical Pursuit Intelligence lifecycle:

    identity → authenticated user → demo workspace → purchase → org → real workspace

This module names which lane a verified session is in. It does not grant tenant
access; org-scoped routes still require membership verification and RLS.
"""

from __future__ import annotations

from typing import Any, Literal

WorkspaceLane = Literal["none", "demo", "organization"]

# Session anchor for authenticated users without customer org membership.
# Not stored in `organizations`; never used for tenant RLS on real data.
DEMO_WORKSPACE_SESSION_ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"

SCHEMA_VERSION = "nf_customer_workspace_lane_v1"


def is_demo_workspace_session_organization(organization_id: Any) -> bool:
    if organization_id is None:
        return False
    return (
        str(organization_id).replace("-", "").lower()
        == DEMO_WORKSPACE_SESSION_ORGANIZATION_ID.replace("-", "").lower()
    )


def resolve_workspace_lane(
    *,
    authenticated: bool,
    session_cookie_valid: bool,
    principal_id: Any = None,
    organization_id: Any = None,
    membership_verified: bool = False,
) -> dict[str, Any]:
    """Derive workspace lane from session facts already measured elsewhere."""
    blocked: list[str] = []
    if not authenticated or not session_cookie_valid or not principal_id:
        lane: WorkspaceLane = "none"
        affiliated = False
        if not authenticated:
            blocked.append("not_authenticated")
        return _result(
            lane=lane,
            affiliated=affiliated,
            organization_id=None,
            blocked=blocked,
        )

    if is_demo_workspace_session_organization(organization_id):
        return _result(
            lane="demo",
            affiliated=False,
            organization_id=None,
            blocked=[],
        )

    if membership_verified and organization_id:
        return _result(
            lane="organization",
            affiliated=True,
            organization_id=str(organization_id),
            blocked=[],
        )

    blocked.append("authenticated_without_affiliation_or_demo_lane")
    return _result(
        lane="none",
        affiliated=False,
        organization_id=None,
        blocked=blocked,
    )


def build_commercial_entitlement_read_model(
    *,
    workspace_lane: WorkspaceLane,
    affiliated: bool,
    provisioning_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal seam only — no payment state is invented."""
    prov = provisioning_status or {}
    if workspace_lane == "organization" and affiliated:
        return {
            "schema_version": "nf_commercial_entitlement_read_model_v1",
            "benefit_access": "unknown",
            "purchase_required_for_real_workspace": False,
            "authority_verified": False,
            "provisioning_status_label": prov.get("customer_status_label"),
            "note": (
                "Organization workspace access is gated by membership and existing "
                "commercial entitlement services on org-scoped routes."
            ),
        }
    return {
        "schema_version": "nf_commercial_entitlement_read_model_v1",
        "benefit_access": "none",
        "purchase_required_for_real_workspace": True,
        "authority_verified": False,
        "provisioning_status_label": prov.get("customer_status_label") or "Demo",
        "commercial_intent_recorded": bool(prov.get("has_request")),
        "note": "Demo workspace is illustrative; purchase and provisioning unlock a real organization workspace.",
    }


def _result(
    *,
    lane: WorkspaceLane,
    affiliated: bool,
    organization_id: str | None,
    blocked: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_lane": lane,
        "affiliated": affiliated,
        "organization_id": organization_id,
        "demo_workspace_session_organization_id": DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
        "blocked_reasons": sorted(set(blocked)),
    }
