"""Tests: Gate 71 capability enforcement on read paths.

These are **adapter-level** tests, not route-level, and that is the finding
rather than a shortcut: no route in the application carries a verified actor, so
there is nothing to attach live enforcement to. Doc 411 records the survey.

What is proved here is that the adapter refuses everything it should — client
role headers, org headers as membership proof, demo operators, anonymous
callers, missing capabilities — and that it permits a read only when a trusted
role arrives from a membership directory.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.api.capability_guard import (
    DRY_RUN,
    LIVE,
    READ_CAPABILITIES,
    READ_ROUTE_CAPABILITY_MAP,
    capability_guard_invariant_failures,
    evaluate_read_capability,
    require_read_capability,
)
from nativeforge.services.rbac_privilege_matrix_service import (
    PERMANENTLY_BLOCKED_CAPABILITIES,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ORG = "11111111-1111-1111-1111-111111111111"

# The identity a verified customer would have once Gate 69/70 land. Nothing in
# the running system can produce this today.
VERIFIED_CUSTOMER = {
    "identity_state": "oidc_verified",
    "verification_trusted": True,
    "subject": "auth0|abc123",
    "issuer": "https://example-tenant.us.auth0.com/",
}


def _allowed(**over: object) -> dict:
    kwargs: dict = {
        "capability": "view_workspace",
        "organization_id": ORG,
        "identity": VERIFIED_CUSTOMER,
        "trusted_role": "viewer",
        "membership_state": "active",
    }
    kwargs.update(over)
    return evaluate_read_capability(**kwargs)


# ── the path that can succeed ───────────────────────────────────────────────


def test_trusted_role_with_capability_is_allowed() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    d = _allowed()
    assert d["blocked_reasons"] == [], d["blocked_reasons"]
    assert d["allowed"] is True
    assert not capability_guard_invariant_failures(d)


@pytest.mark.parametrize(
    "role", ["viewer", "reviewer", "grant_lead", "org_admin", "org_owner"]
)
def test_every_customer_role_can_read_the_workspace(role: str) -> None:
    """view_workspace is held by every customer role in the Gate 57 matrix."""
    assert _allowed(trusted_role=role)["allowed"] is True


def test_dry_run_does_not_claim_enforcement() -> None:
    d = _allowed()
    assert d["mode"] == DRY_RUN
    assert d["enforced"] is False
    assert not capability_guard_invariant_failures(d)


# ── role and capability must not come from the client ───────────────────────


@pytest.mark.parametrize(
    "header", ["X-NF-Role", "x-nf-role", "X-NF-Roles", "X-NF-Capability"]
)
def test_client_asserted_role_headers_are_rejected_not_ignored(header: str) -> None:
    """A silently ignored spoof lets the caller believe it worked."""
    d = _allowed(request_headers={header: "org_owner"})
    assert d["allowed"] is False
    assert d["client_asserted_headers_rejected"] == [header.lower()]
    assert any(
        r.startswith("client_asserted_role_headers_rejected")
        for r in d["blocked_reasons"]
    )


def test_client_role_header_cannot_substitute_for_a_trusted_role() -> None:
    d = evaluate_read_capability(
        capability="view_workspace",
        organization_id=ORG,
        identity=VERIFIED_CUSTOMER,
        trusted_role=None,
        membership_state="active",
        request_headers={"X-NF-Role": "org_owner"},
    )
    assert d["allowed"] is False
    assert "no_trusted_role_from_membership_directory" in d["blocked_reasons"]


def test_there_is_no_parameter_for_a_client_supplied_role() -> None:
    """The cheapest guarantee: no such input exists."""
    import inspect

    params = set(inspect.signature(evaluate_read_capability).parameters)
    for forbidden in ("asserted_role", "client_role", "role_header", "claimed_role"):
        assert forbidden not in params


def test_org_id_is_not_membership_proof() -> None:
    """X-NF-Org-Id gets a request into an org's routes. It proves nothing else."""
    d = evaluate_read_capability(
        capability="view_workspace",
        organization_id=ORG,  # the header value, in effect
        identity=VERIFIED_CUSTOMER,
        trusted_role=None,
        membership_state=None,
    )
    assert d["allowed"] is False
    assert "no_trusted_role_from_membership_directory" in d["blocked_reasons"]


def test_membership_must_be_active_not_merely_present() -> None:
    for state in ("invited", "suspended", "removed", "unknown", None):
        d = _allowed(membership_state=state)
        assert d["allowed"] is False, state


# ── identity boundaries ─────────────────────────────────────────────────────


def test_anonymous_denied() -> None:
    d = _allowed(identity=None, trusted_role=None, membership_state=None)
    assert d["allowed"] is False
    assert any(
        r.startswith("identity_is_not_a_verified_customer")
        for r in d["blocked_reasons"]
    )


def test_demo_operator_is_not_a_customer() -> None:
    """Cloudflare Access proves an operator reached the edge, not that a
    customer logged in."""
    demo = {
        "identity_state": "demo_operator",
        "verification_trusted": False,
        "email": "operator@example.com",
    }
    d = _allowed(identity=demo)
    assert d["allowed"] is False
    assert "identity_is_not_a_verified_customer:demo_operator" in d["blocked_reasons"]


@pytest.mark.parametrize(
    "state",
    ["anonymous", "demo_operator", "oidc_unconfigured", "oidc_configured_unverified"],
)
def test_no_currently_reachable_identity_state_is_a_customer(state: str) -> None:
    """Every state the running system can produce must deny."""
    d = _allowed(identity={"identity_state": state, "verification_trusted": True})
    assert d["allowed"] is False


def test_verification_trusted_false_denies_even_when_state_looks_right() -> None:
    d = _allowed(
        identity={"identity_state": "oidc_verified", "verification_trusted": False}
    )
    assert d["allowed"] is False


# ── capability boundaries ───────────────────────────────────────────────────


def test_role_without_the_capability_is_denied() -> None:
    """viewer holds view_workspace but not view_org_audit_events."""
    d = _allowed(capability="view_org_audit_events", trusted_role="viewer")
    assert d["allowed"] is False


def test_org_owner_holds_the_audit_read_capability() -> None:
    d = _allowed(capability="view_org_audit_events", trusted_role="org_owner")
    assert d["allowed"] is True


@pytest.mark.parametrize(
    "capability",
    [
        "draft_package",
        "assemble_evidence",
        "manage_seats",
        "certify_org_facts",
        "approve_package_readiness",
        "final_application_package_signoff",
    ],
)
def test_write_and_authority_capabilities_are_not_wired_here(capability: str) -> None:
    """This gate wires reads only."""
    d = _allowed(capability=capability, trusted_role="org_owner")
    assert d["allowed"] is False
    assert any(
        r.startswith("capability_not_a_wired_read_capability")
        for r in d["blocked_reasons"]
    )


@pytest.mark.parametrize("capability", sorted(PERMANENTLY_BLOCKED_CAPABILITIES))
def test_permanently_blocked_capabilities_stay_blocked(capability: str) -> None:
    d = _allowed(capability=capability, trusted_role="org_owner")
    assert d["allowed"] is False


def test_read_capabilities_use_existing_vocabulary_only() -> None:
    """No duplicate capability names were invented for this gate."""
    from nativeforge.services.rbac_privilege_matrix_service import CAPABILITIES

    assert READ_CAPABILITIES <= CAPABILITIES
    assert set(READ_ROUTE_CAPABILITY_MAP.values()) <= CAPABILITIES


def test_route_capability_map_covers_the_surveyed_read_families() -> None:
    assert set(READ_ROUTE_CAPABILITY_MAP) == {
        "workspace_read",
        "evidence_read",
        "feedback_read",
        "package_export_preview",
        "source_registry_read",
        "org_audit_read",
    }


# ── audit integration ───────────────────────────────────────────────────────


def test_denial_routes_events_through_the_audit_sink() -> None:
    d = _allowed(capability="view_org_audit_events", trusted_role="viewer")
    assert d["allowed"] is False
    assert d["audit_sink"]["event_count"] >= 1


def test_sink_in_dry_run_persists_nothing() -> None:
    d = _allowed(identity=None, trusted_role=None)
    assert d["audit_sink"]["persisted"] is False
    assert d["audit_sink"]["accepted"] is True


def test_denial_events_are_accounted_not_dropped() -> None:
    d = _allowed(trusted_role=None)
    sink = d["audit_sink"]
    assert sink["event_count"] == sink["events_refused"]


# ── live mode raises, and is attached to nothing ────────────────────────────


def test_require_read_capability_raises_403_when_denied() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        require_read_capability(
            capability="view_workspace", organization_id=ORG, identity=None
        )
    assert exc.value.status_code == 403


def test_require_read_capability_returns_the_decision_when_allowed() -> None:
    d = require_read_capability(
        capability="view_workspace",
        organization_id=ORG,
        identity=VERIFIED_CUSTOMER,
        trusted_role="viewer",
        membership_state="active",
    )
    assert d["allowed"] is True
    assert d["mode"] == LIVE
    assert d["enforced"] is True


def test_the_guard_is_attached_to_no_route() -> None:
    """The central honesty check of this gate.

    If a future change wires the guard into a route file, this fails and forces
    doc 411 to be updated rather than letting the docs drift.
    """
    api_dir = ROOT / "src" / "nativeforge" / "api"
    importers = [
        p.name
        for p in api_dir.glob("*.py")
        if p.name != "capability_guard.py"
        and "capability_guard" in p.read_text(encoding="utf-8")
    ]
    assert importers == [], (
        f"capability_guard is now imported by {importers}; update doc 411 "
        "and add route-level tests"
    )


def test_route_wiring_status_doc_records_zero_live_routes() -> None:
    doc = (
        ROOT / "docs" / "operations" / "411_GATE71_ROUTE_WIRING_STATUS.md"
    ).read_text(encoding="utf-8")
    assert "Live routes wired: 0" in doc


# ── claims ──────────────────────────────────────────────────────────────────


def test_customer_login_live_stays_false() -> None:
    for d in (_allowed(), _allowed(identity=None)):
        assert d["customer_login_live"] is False
        assert d["production_persistence_claimed"] is False


def test_invariants_reject_an_allow_without_a_trusted_role() -> None:
    d = _allowed(trusted_role=None)
    d["allowed"] = True
    d["blocked_reasons"] = []
    fails = capability_guard_invariant_failures(d)
    assert "allowed_without_trusted_role" in fails


def test_invariants_reject_an_allow_for_a_demo_operator() -> None:
    d = _allowed(
        identity={"identity_state": "demo_operator", "verification_trusted": True}
    )
    d["allowed"] = True
    d["blocked_reasons"] = []
    assert "allowed_for_non_customer_identity" in capability_guard_invariant_failures(d)


def test_invariants_reject_dry_run_claiming_enforcement() -> None:
    d = _allowed()
    d["enforced"] = True
    assert "dry_run_claims_enforcement" in capability_guard_invariant_failures(d)


def test_controlled_customer_pilot_remains_no_go() -> None:
    doc = (
        ROOT / "docs" / "operations" / "412_GATE68A_71_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Controlled customer pilot: NO_GO" in doc
    assert "Production rollout:        NO_GO" in doc
    assert "Customer login live:       NO" in doc
    assert "Production storage live:   NO" in doc
