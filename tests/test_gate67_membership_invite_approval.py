"""Tests: Gate 67 membership invite / approval workflow.

The claim under test is narrow and important: a membership row cannot become
active except through a completed, approved invite raised by someone holding
``manage_seats``. Almost every test here is a refusal, because the risk this
gate exists to close is an internal operator writing themselves into a customer
organization.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.domain.enums import AuditAction
from nativeforge.services.membership_invite_approval_service import (
    APPROVAL_STATES,
    INVITE_STATES,
    evaluate_invite,
    evaluate_membership_expiry,
    evaluate_membership_provenance,
    evaluate_membership_revocation,
    evaluate_role_change,
    invite_invariant_failures,
    lifecycle_invariant_failures,
    role_change_invariant_failures,
)
from nativeforge.services.org_tenant_seat_model_service import DEFAULT_SEAT_CAP

ROOT = pathlib.Path(__file__).resolve().parents[1]
ORG = "org-profile-1"

# An invite that is about to become an active membership. Individual fields get
# broken to prove each one is load-bearing.
GOOD = {
    "invite_id": "inv-1",
    "organization_id": ORG,
    "requested_role": "grant_lead",
    "requested_by": "owner-1",
    "requested_by_role": "org_owner",
    "invited_subject": "auth0|abc123",
    "invited_issuer": "https://example-tenant.us.auth0.com/",
    "invite_state": "accepted",
    "approval_required": True,
    "approval_state": "approved",
    "approved_by": "admin-1",
    "approved_by_role": "org_admin",
    "seat_cap": DEFAULT_SEAT_CAP,
    "seat_count": 2,
}


def _events(result: dict, action: AuditAction) -> list[dict]:
    return [e for e in result["audit_events"] if e["event_type"] == action.value]


# ── the happy path must exist ───────────────────────────────────────────────


def test_approved_accepted_invite_activates_membership() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    r = evaluate_invite(**GOOD)
    assert r["blocked_reasons"] == []
    assert r["allowed"] is True
    assert r["membership_state_after_acceptance"] == "active"
    assert r["can_activate_membership"] is True
    assert not invite_invariant_failures(r)


def test_activation_emits_membership_created_unpersisted() -> None:
    r = evaluate_invite(**GOOD)
    created = _events(r, AuditAction.membership_created)
    assert len(created) == 1
    assert created[0]["detail"]["provenance"] == "completed_invite"
    assert created[0]["persisted"] is False


# ── invite state ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "state", ["draft", "pending_approval", "expired", "revoked", "rejected"]
)
def test_non_accepted_invite_states_do_not_activate(state: str) -> None:
    r = evaluate_invite(**{**GOOD, "invite_state": state})
    assert r["can_activate_membership"] is False
    assert r["membership_state_after_acceptance"] in {"none", "pending_approval"}


@pytest.mark.parametrize("state", ["expired", "revoked", "rejected"])
def test_dead_invite_states_deny(state: str) -> None:
    r = evaluate_invite(**{**GOOD, "invite_state": state})
    assert r["allowed"] is False
    assert f"invite_state_denies:{state}" in r["blocked_reasons"]


def test_unknown_invite_state_denies() -> None:
    r = evaluate_invite(**{**GOOD, "invite_state": "totally_made_up"})
    assert r["allowed"] is False
    assert r["invite_state"] == "unknown"
    assert "invite_state_unknown" in r["blocked_reasons"]


def test_revocation_timestamp_overrides_the_state_column() -> None:
    """Trusting the column over the timestamp is how a revoked invite gets in."""
    r = evaluate_invite(**{**GOOD, "revoked_at": "2026-01-01T00:00:00Z"})
    assert r["invite_state"] == "revoked"
    assert r["allowed"] is False


def test_expiry_is_evaluated_against_caller_supplied_now() -> None:
    base = {**GOOD, "invite_state": "sent", "expires_at": "2026-06-01T00:00:00Z"}
    before = evaluate_invite(**base, now="2026-05-01T00:00:00Z")
    assert before["invite_state"] == "sent"
    after = evaluate_invite(**base, now="2026-07-01T00:00:00Z")
    assert after["invite_state"] == "expired"
    assert after["allowed"] is False


def test_denying_invite_states_are_derived_not_listed() -> None:
    """A state added later must deny until someone deliberately permits it."""
    from nativeforge.services.membership_invite_approval_service import (
        INVITE_DENYING_STATES,
        INVITE_LIVE_STATES,
    )

    assert INVITE_LIVE_STATES | INVITE_DENYING_STATES == INVITE_STATES
    assert not (INVITE_LIVE_STATES & INVITE_DENYING_STATES)


# ── approval ────────────────────────────────────────────────────────────────


def test_accepted_invite_without_approval_cannot_activate() -> None:
    """Acceptance is not activation. This is the core rule of the gate."""
    r = evaluate_invite(
        **{
            **GOOD,
            "approval_state": "pending",
            "approved_by": None,
            "approved_by_role": None,
        }
    )
    assert r["can_activate_membership"] is False
    assert r["allowed"] is False
    assert "approval_state_denies:pending" in r["blocked_reasons"]


@pytest.mark.parametrize(
    "state", ["required", "pending", "rejected", "expired", "revoked"]
)
def test_unsatisfied_approval_states_deny(state: str) -> None:
    r = evaluate_invite(**{**GOOD, "approval_state": state})
    assert r["allowed"] is False
    assert f"approval_state_denies:{state}" in r["blocked_reasons"]


def test_unknown_approval_state_denies() -> None:
    r = evaluate_invite(**{**GOOD, "approval_state": "probably_fine"})
    assert r["approval_state"] == "unknown"
    assert r["allowed"] is False
    assert "approval_state_denies:unknown" in r["blocked_reasons"]


def test_approval_claimed_without_an_approver_denies() -> None:
    r = evaluate_invite(**{**GOOD, "approved_by": None})
    assert r["allowed"] is False
    assert "approval_claimed_without_approver" in r["blocked_reasons"]


def test_denying_approval_states_are_derived_not_listed() -> None:
    from nativeforge.services.membership_invite_approval_service import (
        APPROVAL_DENYING_STATES,
        APPROVAL_SATISFIED_STATES,
    )

    assert APPROVAL_SATISFIED_STATES | APPROVAL_DENYING_STATES == APPROVAL_STATES
    assert not (APPROVAL_SATISFIED_STATES & APPROVAL_DENYING_STATES)


def test_not_required_approval_can_activate() -> None:
    r = evaluate_invite(
        **{
            **GOOD,
            "approval_required": False,
            "approval_state": "not_required",
            "approved_by": None,
            "approved_by_role": None,
        }
    )
    assert r["allowed"] is True
    assert r["can_activate_membership"] is True


def test_approval_is_required_by_default() -> None:
    """The default must be the safe one."""
    import inspect

    sig = inspect.signature(evaluate_invite)
    assert sig.parameters["approval_required"].default is True


# ── authorization: the gap the survey found ─────────────────────────────────


@pytest.mark.parametrize(
    "role",
    [
        "viewer",
        "reviewer",
        "grant_lead",
        "authorized_representative",
        "operator_internal",
        "unknown",
        None,
    ],
)
def test_inviter_without_manage_seats_denied(role: str | None) -> None:
    """evaluate_seat_invite records the actor and never checks them. This does."""
    r = evaluate_invite(**{**GOOD, "requested_by_role": role})
    assert r["allowed"] is False
    assert any(
        b.startswith("inviter_lacks_manage_seats") for b in r["blocked_reasons"]
    ), r["blocked_reasons"]


@pytest.mark.parametrize("role", ["org_owner", "org_admin"])
def test_roles_holding_manage_seats_may_invite(role: str) -> None:
    r = evaluate_invite(**{**GOOD, "requested_by_role": role})
    assert r["allowed"] is True


@pytest.mark.parametrize(
    "role", ["viewer", "reviewer", "grant_lead", "authorized_representative", None]
)
def test_approver_without_manage_seats_denied(role: str | None) -> None:
    r = evaluate_invite(**{**GOOD, "approved_by_role": role})
    assert r["allowed"] is False
    assert any(
        b.startswith("approver_lacks_manage_seats") for b in r["blocked_reasons"]
    )


def test_missing_inviter_denied() -> None:
    r = evaluate_invite(**{**GOOD, "requested_by": ""})
    assert r["allowed"] is False
    assert "inviter_missing" in r["blocked_reasons"]


def test_seat_management_capability_comes_from_the_rbac_matrix() -> None:
    """Hardcoding a role list here would let the matrix drift away silently."""
    from nativeforge.services.rbac_privilege_matrix_service import ROLE_CAPABILITIES

    holders = {r for r, caps in ROLE_CAPABILITIES.items() if "manage_seats" in caps}
    assert holders == {"org_owner", "org_admin"}


# ── roles ───────────────────────────────────────────────────────────────────


def test_operator_internal_cannot_be_invited_as_customer_role() -> None:
    r = evaluate_invite(**{**GOOD, "requested_role": "operator_internal"})
    assert r["allowed"] is False
    assert "internal_role_cannot_be_invited_as_customer_role" in r["blocked_reasons"]
    assert r["can_activate_membership"] is False


def test_unknown_requested_role_denied() -> None:
    r = evaluate_invite(**{**GOOD, "requested_role": "superuser"})
    assert r["requested_role"] == "unknown"
    assert r["allowed"] is False
    assert "requested_role_unknown" in r["blocked_reasons"]


def test_literal_unknown_role_denied() -> None:
    """`unknown` is a valid vocabulary member and must still grant nothing."""
    r = evaluate_invite(**{**GOOD, "requested_role": "unknown"})
    assert r["allowed"] is False
    assert "requested_role_unknown" in r["blocked_reasons"]


# ── seats ───────────────────────────────────────────────────────────────────


def test_fifth_seat_is_allowed() -> None:
    r = evaluate_invite(**{**GOOD, "seat_count": 4})
    assert r["allowed"] is True
    assert r["consumes_seat"] is True


def test_sixth_seat_blocked_without_override() -> None:
    r = evaluate_invite(**{**GOOD, "seat_count": 5})
    assert r["allowed"] is False
    assert "seat_cap_reached_no_override_approval" in r["blocked_reasons"]


def test_override_request_alone_cannot_allow_a_sixth_seat() -> None:
    """A request is not an approval."""
    r = evaluate_invite(**{**GOOD, "seat_count": 5, "seat_override_requested": True})
    assert r["allowed"] is False
    assert "seat_override_requested_but_not_approved" in r["blocked_reasons"]


def test_approved_override_allows_a_sixth_seat() -> None:
    r = evaluate_invite(
        **{
            **GOOD,
            "seat_count": 5,
            "seat_override_requested": True,
            "seat_override_approved_by": "admin-2",
            "seat_override_approved_by_role": "org_admin",
        }
    )
    assert r["allowed"] is True
    assert r["seat_override_approved"] is True
    assert not invite_invariant_failures(r)


def test_override_approver_needs_manage_seats() -> None:
    r = evaluate_invite(
        **{
            **GOOD,
            "seat_count": 5,
            "seat_override_approved_by": "viewer-9",
            "seat_override_approved_by_role": "viewer",
        }
    )
    assert r["allowed"] is False
    assert any(
        b.startswith("seat_override_approver_lacks_manage_seats")
        for b in r["blocked_reasons"]
    )


def test_override_cannot_be_self_approved() -> None:
    """Self-approving your own exception is what makes a cap decorative."""
    r = evaluate_invite(
        **{
            **GOOD,
            "seat_count": 5,
            "seat_override_approved_by": GOOD["requested_by"],
            "seat_override_approved_by_role": "org_owner",
        }
    )
    assert r["allowed"] is False
    assert "seat_override_self_approved" in r["blocked_reasons"]


def test_invariants_catch_a_cap_breach_without_override() -> None:
    r = evaluate_invite(**{**GOOD, "seat_count": 5})
    r["allowed"] = True
    r["blocked_reasons"] = []
    assert "seat_cap_exceeded_without_override" in invite_invariant_failures(r)


# ── provenance: direct writes are not trusted ───────────────────────────────


def test_completed_invite_provenance_is_trusted() -> None:
    r = evaluate_membership_provenance(
        organization_id=ORG,
        subject_id="auth0|abc",
        provenance="completed_invite",
        invite_id="inv-1",
    )
    assert r["trusted"] is True
    assert r["blocked_reasons"] == []


@pytest.mark.parametrize(
    "prov", ["operator_direct_write", "migration_backfill", "unknown", "made_up"]
)
def test_direct_membership_creation_is_not_trusted(prov: str) -> None:
    """The risk this gate exists to close."""
    r = evaluate_membership_provenance(
        organization_id=ORG,
        subject_id="auth0|abc",
        provenance=prov,
        actor_id="operator-1",
    )
    assert r["trusted"] is False
    assert any(
        b.startswith("untrusted_membership_provenance") for b in r["blocked_reasons"]
    )
    assert _events(r, AuditAction.authority_sensitive_action_blocked)


def test_invite_provenance_without_an_invite_id_is_unfalsifiable_and_denied() -> None:
    r = evaluate_membership_provenance(
        organization_id=ORG,
        subject_id="auth0|abc",
        provenance="completed_invite",
        invite_id=None,
    )
    assert r["trusted"] is False
    assert "completed_invite_provenance_without_invite_id" in r["blocked_reasons"]


# ── role change ─────────────────────────────────────────────────────────────

ROLE_CHANGE = {
    "organization_id": ORG,
    "subject_id": "auth0|abc",
    "old_role": "viewer",
    "new_role": "grant_lead",
    "actor_id": "owner-1",
    "actor_role": "org_owner",
}


def test_role_change_by_trusted_approver_is_allowed_and_audited() -> None:
    r = evaluate_role_change(**ROLE_CHANGE)
    assert r["allowed"] is True
    assert r["new_role"] == "grant_lead"
    assert _events(r, AuditAction.role_changed)
    assert not role_change_invariant_failures(r)


@pytest.mark.parametrize("role", ["viewer", "reviewer", "grant_lead", None])
def test_role_change_requires_manage_seats(role: str | None) -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "actor_role": role})
    assert r["allowed"] is False
    assert any(b.startswith("actor_lacks_manage_seats") for b in r["blocked_reasons"])
    # A denied change must not alter the role.
    assert r["new_role"] == r["old_role"]


def test_denied_role_change_emits_a_denial_event() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "actor_role": "viewer"})
    assert _events(r, AuditAction.tenant_access_denied)
    assert not _events(r, AuditAction.role_changed)


def test_upgrade_and_downgrade_are_distinguishable() -> None:
    up = evaluate_role_change(**ROLE_CHANGE)
    assert up["direction"] == "upgrade"
    down = evaluate_role_change(
        **{**ROLE_CHANGE, "old_role": "org_admin", "new_role": "viewer"}
    )
    assert down["direction"] == "downgrade"


def test_privilege_escalation_is_flagged() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "new_role": "org_admin"})
    assert r["allowed"] is True
    assert r["is_privilege_escalation"] is True


def test_role_change_never_grants_authority_immediately() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "new_role": "authorized_representative"})
    assert r["grants_customer_authority_immediately"] is False


def test_cannot_change_into_operator_internal() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "new_role": "operator_internal"})
    assert r["allowed"] is False
    assert "cannot_change_customer_role_to_internal_role" in r["blocked_reasons"]


def test_cannot_change_out_of_operator_internal_through_this_path() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "old_role": "operator_internal"})
    assert r["allowed"] is False


def test_no_op_role_change_denied() -> None:
    r = evaluate_role_change(**{**ROLE_CHANGE, "new_role": "viewer"})
    assert r["allowed"] is False
    assert "no_op_role_change" in r["blocked_reasons"]


# ── revocation and expiry ───────────────────────────────────────────────────


def test_revocation_by_trusted_actor_emits_membership_revoked() -> None:
    r = evaluate_membership_revocation(
        organization_id=ORG,
        subject_id="auth0|abc",
        actor_id="owner-1",
        actor_role="org_owner",
        reason="left the organization",
    )
    assert r["allowed"] is True
    assert r["membership_state_after"] == "revoked"
    assert r["seat_released"] is True
    assert _events(r, AuditAction.membership_revoked)
    assert not lifecycle_invariant_failures(r)


def test_revocation_requires_manage_seats() -> None:
    r = evaluate_membership_revocation(
        organization_id=ORG,
        subject_id="auth0|abc",
        actor_id="v-1",
        actor_role="viewer",
    )
    assert r["allowed"] is False
    assert r["membership_state_after"] == "unchanged"
    assert r["seat_released"] is False
    assert _events(r, AuditAction.tenant_access_denied)


def test_expiry_emits_membership_expired_and_needs_no_actor() -> None:
    """Expiry is a fact about time, not an action someone must remember."""
    r = evaluate_membership_expiry(
        organization_id=ORG,
        subject_id="auth0|abc",
        expires_at="2026-06-01T00:00:00Z",
        now="2026-07-01T00:00:00Z",
    )
    assert r["expired"] is True
    assert r["membership_state_after"] == "expired"
    assert _events(r, AuditAction.membership_expired)
    assert not lifecycle_invariant_failures(r)


def test_unexpired_membership_emits_nothing() -> None:
    r = evaluate_membership_expiry(
        organization_id=ORG,
        subject_id="auth0|abc",
        expires_at="2026-06-01T00:00:00Z",
        now="2026-05-01T00:00:00Z",
    )
    assert r["expired"] is False
    assert r["audit_events"] == []


def test_membership_with_no_expiry_never_expires() -> None:
    r = evaluate_membership_expiry(
        organization_id=ORG,
        subject_id="auth0|abc",
        expires_at=None,
        now="2099-01-01T00:00:00Z",
    )
    assert r["expired"] is False


# ── nothing is persisted, nothing is claimed ────────────────────────────────


def test_every_emitted_event_is_unpersisted() -> None:
    results = [
        evaluate_invite(**GOOD),
        evaluate_invite(**{**GOOD, "requested_by_role": "viewer"}),
        evaluate_role_change(**ROLE_CHANGE),
        evaluate_membership_revocation(
            organization_id=ORG,
            subject_id="s",
            actor_id="owner-1",
            actor_role="org_owner",
        ),
        evaluate_membership_expiry(
            organization_id=ORG,
            subject_id="s",
            expires_at="2026-01-01T00:00:00Z",
            now="2026-02-01T00:00:00Z",
        ),
        evaluate_membership_provenance(
            organization_id=ORG, subject_id="s", provenance="operator_direct_write"
        ),
    ]
    for r in results:
        assert r["persisted"] is False
        for event in r["audit_events"]:
            assert event["persisted"] is False, event


def test_no_path_emits_the_unpersistable_cross_org_verb() -> None:
    """Gate 65 established this cannot be represented by the current schema."""
    for r in (
        evaluate_invite(**GOOD),
        evaluate_invite(**{**GOOD, "seat_count": 9}),
        evaluate_role_change(**{**ROLE_CHANGE, "actor_role": "viewer"}),
    ):
        types = {e["event_type"] for e in r["audit_events"]}
        assert AuditAction.cross_org_access_attempt.value not in types


def test_customer_login_live_stays_false() -> None:
    assert evaluate_invite(**GOOD)["customer_login_live"] is False


def test_invite_never_carries_customer_authority() -> None:
    r = evaluate_invite(**{**GOOD, "requested_role": "authorized_representative"})
    assert r["carries_customer_authority"] is False


def test_invariants_reject_a_forged_activation() -> None:
    r = evaluate_invite(**{**GOOD, "approval_state": "pending"})
    r["can_activate_membership"] = True
    fails = invite_invariant_failures(r)
    assert "activation_while_denied" in fails
    assert "activation_without_satisfied_approval" in fails


def test_controlled_customer_pilot_remains_no_go() -> None:
    doc = (
        ROOT / "docs" / "operations" / "407_GATE67_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Controlled customer pilot: NO_GO" in doc
    assert "Production rollout:        NO_GO" in doc
    assert "Customer login live:       NO" in doc
    assert "Production storage live:   NO" in doc
