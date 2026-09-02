"""Gate 136: the second-person invite flow is executable, and refuses correctly.

Gate 135 proved the last `customer_auth_live` blocker was an event. This gate
makes the event runnable in minutes, and everything below is about the same
question: can it be run *wrongly*?

The three refusals Gate 136A found missing from `record_acceptance` -
expired, already accepted, and accepter-does-not-match-the-invite - each get a
test that reaches them, because a refusal nothing can trigger is not a refusal.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import dev_org_membership_bootstrap_service as boot_svc
from nativeforge.services import membership_invite_activation_service as activation
from nativeforge.services import membership_invite_repository_service as invite_repo
from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ORGANIZATION_ID,
    REFUSED_ORGANIZATION_ID,
    build_customer_auth_activation_decision,
)

DEMO_ORG = APPROVED_ORGANIZATION_ID
REAL_ORG = REFUSED_ORGANIZATION_ID
ISSUER = "https://accounts.google.com"
NOW = datetime(2026, 9, 2, tzinfo=UTC)
LATER = NOW + timedelta(days=7)

OWNER_EMAIL = "owner@example.test"
INVITED_EMAIL = "second.person@example.test"
STRANGER_EMAIL = "stranger@example.test"

ISSUE_SCRIPT = "scripts/nativeforge_demo_invite_issue.py"
ACCEPT_SCRIPT = "scripts/nativeforge_demo_invite_accept.py"
VERIFIER = "scripts/verify_nativeforge_customer_auth_live.sh"

ORGANIZATIONS = sa.Table(
    "organizations",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def activation_db():
    """Organizations, identities, memberships and invites, in memory."""
    engine = sa.create_engine("sqlite://")
    ORGANIZATIONS.create(engine)
    boot_svc.IDENTITIES.create(engine)
    boot_svc.MEMBERSHIPS.create(engine)
    invite_repo.INVITES.create(engine)
    with engine.begin() as conn:
        for org_id, org_type in ((REAL_ORG, "real"), (DEMO_ORG, "demo")):
            conn.execute(
                sa.insert(ORGANIZATIONS).values(
                    id=uuid.UUID(org_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=NOW,
                )
            )
        yield conn
    engine.dispose()


def _identity(conn, subject: str, email: str | None = None) -> str:
    return boot_svc.upsert_identity(
        connection=conn,
        issuer=ISSUER,
        subject=subject,
        email=email,
        email_verified=True,
        verification_source="oidc_token_signature",
        now=NOW,
    )["identity_id"]


def _owner(conn, organization_id: str = DEMO_ORG) -> str:
    identity_id = _identity(conn, f"g136-owner-{organization_id[:4]}", OWNER_EMAIL)
    boot_svc.insert_membership(
        connection=conn,
        organization_id=organization_id,
        identity_id=identity_id,
        state="active",
        role="org_owner",
        membership_source="org_owner_approved",
        approved_by=identity_id,
        now=NOW,
    )
    return identity_id


def _issue(
    conn,
    owner: str,
    *,
    invite_id: str = "nf-invite-g136",
    organization_id: str = DEMO_ORG,
    invited_email: str | None = INVITED_EMAIL,
    expires_at: str | None = None,
    **overrides,
):
    fields = {
        "invite_id": invite_id,
        "requested_role": "grant_lead",
        "requested_by": owner,
        "requested_by_role": "org_owner",
        "invited_email": invited_email,
        "invite_state": "approved",
        "approval_required": True,
        "approval_state": "approved",
        "approved_by": owner,
        "approved_by_role": "org_owner",
        "seat_cap": 5,
        "seat_count": 1,
        "expires_at": expires_at or LATER.isoformat(),
        "now": NOW.isoformat(),
    }
    fields.update(overrides)
    return invite_repo.insert_invite(
        connection=conn,
        organization_id=organization_id,
        created_at=NOW,
        **fields,
    )


# ---------------------------------------------------------------------------
# 136B: the issue command
# ---------------------------------------------------------------------------


def _run_script(script: str, *argv: str, env_extra: dict[str, str] | None = None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, script, *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path.cwd()),
    )


def test_the_invite_command_refuses_the_real_org():
    """Named, so nobody has to recognise the uuid."""
    proc = _run_script(
        ISSUE_SCRIPT,
        "--email",
        INVITED_EMAIL,
        "--organization",
        REAL_ORG,
        "--json",
    )
    assert proc.returncode == 2
    status = json.loads(proc.stdout)
    assert status["issued"] is False
    assert (
        "organization_is_the_explicitly_refused_real_org" in status["blocked_reasons"]
    )


def test_the_invite_command_refuses_an_organization_outside_the_scope():
    proc = _run_script(
        ISSUE_SCRIPT,
        "--email",
        INVITED_EMAIL,
        "--organization",
        "cccccccc-dddd-eeee-ffff-000000000000",
        "--json",
    )
    assert proc.returncode == 2
    status = json.loads(proc.stdout)
    assert "organization_outside_the_approved_scope" in status["blocked_reasons"]


def test_the_invite_command_refuses_production():
    """The refusal is reachable, which is the only way it means anything."""
    proc = _run_script(
        ISSUE_SCRIPT,
        "--email",
        INVITED_EMAIL,
        "--json",
        env_extra={"NF_APP_ENV": "production"},
    )
    assert proc.returncode == 2
    status = json.loads(proc.stdout)
    assert status["issued"] is False
    assert any(
        r.startswith("environment_outside_the_approved_scope")
        for r in status["blocked_reasons"]
    )


def test_the_invite_command_prints_no_address_or_subject():
    """The address goes in as an argument and does not come back out."""
    proc = _run_script(
        ISSUE_SCRIPT,
        "--email",
        INVITED_EMAIL,
        "--organization",
        REAL_ORG,
        "--json",
    )
    combined = proc.stdout + proc.stderr
    assert INVITED_EMAIL not in combined
    assert "second.person" not in combined
    for forbidden in ("subject", "id_token", "access_token", "cookie"):
        assert forbidden not in combined.lower()


def test_neither_script_can_print_a_provider_subject():
    """Parsed, not grepped: the scripts never name the field at all."""
    for script in (ISSUE_SCRIPT, ACCEPT_SCRIPT):
        source = Path(script).read_text(encoding="utf-8")
        tree = __import__("ast").parse(source)
        printed = [
            node
            for node in __import__("ast").walk(tree)
            if isinstance(node, __import__("ast").Call)
            and isinstance(node.func, __import__("ast").Name)
            and node.func.id == "print"
        ]
        assert printed, script
        rendered = "\n".join(__import__("ast").unparse(node) for node in printed)
        for forbidden in ("subject", "verifier", "cookie", "token", "state"):
            assert forbidden not in rendered.lower(), (script, forbidden)


# ---------------------------------------------------------------------------
# 136C: the accept path
# ---------------------------------------------------------------------------


def test_a_pending_invite_cannot_even_be_recorded(activation_db):
    """A stronger claim than "does not satisfy the gate", and the true one.

    `evaluate_invite` refuses to store an invite still awaiting approval at
    all, so a pending invite cannot reach the evidence to fail it. Measured
    while writing this test - the first version inserted one and asserted the
    gate stayed false, which would have passed for the wrong reason: the row
    was never there.
    """
    owner = _owner(activation_db)
    result = _issue(
        activation_db,
        owner,
        invite_state="pending_approval",
        approval_state="pending",
        approved_by=None,
        approved_by_role=None,
    )
    assert result["rows_written"] == 0
    assert "invite_state_denies:pending_approval" in result["blocked_reasons"]
    assert "approval_state_denies:pending" in result["blocked_reasons"]

    evidence = invite_repo.build_invite_binding_evidence(connection=activation_db)
    assert evidence["invite_rows"] == 0
    assert evidence["invite_binding_passed"] is False
    assert "no_invite_has_been_recorded" in evidence["blocked_reasons"]


def test_an_approved_invite_alone_does_not_satisfy_the_gate(activation_db):
    owner = _owner(activation_db)
    _issue(activation_db, owner)
    evidence = invite_repo.build_invite_binding_evidence(connection=activation_db)
    assert evidence["approved_invite_rows"] == 1
    assert evidence["accepted_invite_rows"] == 0
    assert evidence["invite_binding_passed"] is False


def test_a_completed_invite_plus_a_membership_satisfies_the_gate(activation_db):
    """The whole flow, through the service the script calls."""
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner)

    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert result["membership_activated"] is True
    assert result["invite_accepted"] is True
    assert result["membership_rows_written"] == 1
    assert result["accepter_matched_the_invite"] is True
    assert result["provenance"] == "completed_invite"
    assert result["invite_binding_passed"] is True
    assert result["blocked_reasons"] == []
    assert activation.activation_invariant_failures(result) == []

    evidence = invite_repo.build_invite_binding_evidence(connection=activation_db)
    assert evidence["memberships_from_a_completed_invite"] == 1
    assert evidence["invite_binding_passed"] is True


def test_the_membership_it_writes_names_the_invite(activation_db):
    """Migration 0039's whole purpose, asserted on the row.

    Before this the evidence inferred invite provenance from a shared identity
    id, so an operator-written membership for somebody who separately accepted
    an invite counted.
    """
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner)
    activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )

    row = (
        activation_db.execute(
            sa.select(boot_svc.MEMBERSHIPS).where(
                boot_svc.MEMBERSHIPS.c.identity_id == uuid.UUID(invitee)
            )
        )
        .mappings()
        .one()
    )
    assert row["invite_id"] == "nf-invite-g136"
    assert str(row["invited_by"]).replace("-", "") == owner.replace("-", "")
    assert row["membership_source"] == "org_owner_approved"
    assert row["is_demo"] is True


def test_a_membership_that_shares_an_identity_but_not_the_invite_does_not_count(
    activation_db,
):
    """The exact defect 0039 closed, kept reachable so it cannot come back."""
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner)
    invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    # Written directly, naming no invite. This is what used to pass.
    boot_svc.insert_membership(
        connection=activation_db,
        organization_id=DEMO_ORG,
        identity_id=invitee,
        state="active",
        role="grant_lead",
        membership_source="org_owner_approved",
        approved_by=owner,
        now=NOW,
    )

    evidence = invite_repo.build_invite_binding_evidence(connection=activation_db)
    assert evidence["accepted_invite_rows"] == 1
    assert evidence["memberships_matching_an_accepter_by_identity_only"] == 1
    assert evidence["memberships_from_a_completed_invite"] == 0
    assert evidence["invite_binding_passed"] is False
    assert (
        "membership_shares_an_identity_but_does_not_name_the_invite"
        in evidence["blocked_reasons"]
    )


def test_a_self_invite_is_refused(activation_db):
    """Owner requests, owner approves, owner accepts."""
    owner = _owner(activation_db)
    result = _issue(activation_db, owner)
    assert result["rows_written"] == 1

    accepted = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=owner,
        now=NOW,
    )
    assert accepted["accepted"] is False
    assert accepted["self_dealt"] is True
    assert invite_repo.SELF_DEALT in accepted["blocked_reasons"]


def test_the_owner_cannot_accept_their_own_invite_through_the_activation_service(
    activation_db,
):
    owner = _owner(activation_db)
    _issue(activation_db, owner)
    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=owner,
        now=NOW,
    )
    assert result["membership_activated"] is False
    assert result["membership_rows_written"] == 0
    # They are already a member, which is true and is reported first.
    assert activation.ALREADY_A_MEMBER in result["blocked_reasons"]


def test_an_uninvited_identity_cannot_accept(activation_db):
    """The refusal Gate 136A found absent, reached on its own."""
    owner = _owner(activation_db)
    _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    stranger = _identity(activation_db, "g136-stranger", STRANGER_EMAIL)
    _issue(activation_db, owner)

    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=stranger,
        now=NOW,
    )
    assert result["membership_activated"] is False
    assert result["accepter_matched_the_invite"] is False
    assert invite_repo.ACCEPTER_NOT_INVITED in result["blocked_reasons"]


def test_an_invite_naming_nobody_admits_nobody(activation_db):
    """Deny by default. No fingerprint and no domain identifies no person."""
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner, invited_email=None)

    accepted = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert accepted["accepted"] is False
    assert invite_repo.ACCEPTER_NOT_INVITED in accepted["blocked_reasons"]


def test_an_invite_with_only_a_domain_matches_on_the_domain(activation_db):
    """The fallback branch, and the only rows that can reach it.

    Gate 135's invites stored `invited_email_domain` and no fingerprint - the
    column did not exist. There are zero such rows in the dev database, so
    without this the branch would be unreachable, and an unreachable branch is
    how a match that does not match gets written.

    The row is constructed directly because the issue path cannot produce one
    any more, which is the honest way to say "this is for legacy rows".
    """
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner)
    activation_db.execute(
        sa.update(invite_repo.INVITES)
        .where(invite_repo.INVITES.c.invite_id == "nf-invite-g136")
        .values(invited_email_fingerprint=None)
    )

    accepted = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert accepted["accepted"] is True
    assert accepted["accepter_matched_the_invite"] is True


def test_a_domain_only_invite_still_refuses_another_domain(activation_db):
    owner = _owner(activation_db)
    stranger = _identity(activation_db, "g136-stranger", "someone@elsewhere.invalid")
    _issue(activation_db, owner)
    activation_db.execute(
        sa.update(invite_repo.INVITES)
        .where(invite_repo.INVITES.c.invite_id == "nf-invite-g136")
        .values(invited_email_fingerprint=None)
    )

    accepted = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=stranger,
        now=NOW,
    )
    assert accepted["accepted"] is False
    assert invite_repo.ACCEPTER_NOT_INVITED in accepted["blocked_reasons"]


def test_an_invite_id_too_long_for_a_membership_is_refused(activation_db):
    """Refused before either write, not discovered as a database error.

    The two `invite_id` columns are String(128) and String(64). An id between
    them writes fine as an invite and then cannot be named by the membership it
    produces - on PostgreSQL that is a value-too-long error mid-transaction,
    which reports a driver message instead of a reason.
    """
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    long_id = "nf-invite-" + ("x" * 80)
    assert len(long_id) > activation.MEMBERSHIP_INVITE_ID_MAX
    _issue(activation_db, owner, invite_id=long_id)

    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id=long_id,
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert result["membership_activated"] is False
    assert result["invite_accepted"] is False
    assert activation.INVITE_ID_TOO_LONG in result["blocked_reasons"]

    # And nothing was written by either half.
    evidence = invite_repo.build_invite_binding_evidence(connection=activation_db)
    assert evidence["accepted_invite_rows"] == 0
    assert evidence["invite_binding_passed"] is False


def test_the_issue_script_produces_an_id_a_membership_can_name():
    """The default is well inside the limit, and this is what says so."""
    source = Path(ISSUE_SCRIPT).read_text(encoding="utf-8")
    assert 'f"nf-invite-{uuid.uuid4().hex[:12]}"' in source
    assert len("nf-invite-" + "0" * 12) <= activation.MEMBERSHIP_INVITE_ID_MAX


def test_an_expired_invite_cannot_be_accepted(activation_db):
    """`evaluate_invite` derived expiry from the timestamp; this did not."""
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(
        activation_db,
        owner,
        expires_at=(NOW + timedelta(days=1)).isoformat(),
    )

    accepted = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW + timedelta(days=2),
    )
    assert accepted["accepted"] is False
    assert invite_repo.INVITE_EXPIRED in accepted["blocked_reasons"]


def test_an_invite_cannot_be_accepted_twice(activation_db):
    """Re-accepting would move accepted_by_identity_id to a different person."""
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner)
    first = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert first["accepted"] is True

    again = invite_repo.record_acceptance(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert again["accepted"] is False
    assert invite_repo.ALREADY_ACCEPTED in again["blocked_reasons"]


def test_the_activation_service_refuses_a_real_organization(activation_db):
    """Demo scope, derived from organizations.org_type."""
    owner = _owner(activation_db, REAL_ORG)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner, organization_id=REAL_ORG)

    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=REAL_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert result["membership_activated"] is False
    assert result["membership_rows_written"] == 0
    assert activation.NOT_DEMO in result["blocked_reasons"]


def test_an_identity_that_never_signed_in_cannot_be_resolved(activation_db):
    """The normal answer before the invited person logs in."""
    _owner(activation_db)
    resolved = activation.resolve_invited_identity(
        connection=activation_db, email=INVITED_EMAIL
    )
    assert resolved["identity_resolved"] is False
    assert resolved["candidates"] == 0
    assert activation.IDENTITY_NOT_FOUND in resolved["blocked_reasons"]
    assert resolved["invited_email_recorded"] is False


def test_resolution_returns_a_fingerprint_and_never_the_address(activation_db):
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    resolved = activation.resolve_invited_identity(
        connection=activation_db, email=INVITED_EMAIL.upper()
    )
    assert resolved["identity_resolved"] is True
    assert resolved["identity_id"] == invitee
    assert INVITED_EMAIL not in json.dumps(resolved)
    assert resolved["invited_email_fingerprint"] == invite_repo.email_fingerprint(
        INVITED_EMAIL
    )


def test_the_seat_cap_is_counted_at_acceptance_not_at_issue(activation_db):
    """Two seats, both taken between issuing and accepting.

    `evaluate_invite` checks the cap against the count it is *given* when the
    invite is written, which is the honest number at that moment and not at the
    moment somebody accepts. The gap is real - the invite here is valid when
    issued - so the acceptance counts again.
    """
    owner = _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    _issue(activation_db, owner, seat_cap=2, seat_count=1)

    # Somebody else takes the second seat first.
    other = _identity(activation_db, "g136-other", "other@example.test")
    boot_svc.insert_membership(
        connection=activation_db,
        organization_id=DEMO_ORG,
        identity_id=other,
        state="active",
        role="viewer",
        membership_source="org_owner_approved",
        approved_by=owner,
        now=NOW,
    )

    result = activation.accept_invite_and_create_membership(
        connection=activation_db,
        invite_id="nf-invite-g136",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert result["membership_activated"] is False
    assert activation.SEAT_CAP_REACHED in result["blocked_reasons"]
    assert result["seat_count_before"] == 2
    assert result["seat_cap"] == 2


def test_a_full_organization_refuses_the_invite_at_issue_time_too(activation_db):
    """The other half of the same cap, so neither check carries it alone."""
    owner = _owner(activation_db)
    result = _issue(activation_db, owner, seat_cap=1, seat_count=1)
    assert result["rows_written"] == 0
    assert "seat_cap_reached_no_override_approval" in result["blocked_reasons"]


def test_a_membership_naming_an_invite_must_name_the_inviter(activation_db):
    _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    result = boot_svc.insert_membership(
        connection=activation_db,
        organization_id=DEMO_ORG,
        identity_id=invitee,
        state="active",
        role="grant_lead",
        membership_source="org_owner_approved",
        approved_by=invitee,
        invite_id="nf-invite-g136",
        now=NOW,
    )
    assert result["rows_written"] == 0
    assert (
        "membership_names_an_invite_without_naming_the_inviter"
        in result["blocked_reasons"]
    )


def test_nobody_can_invite_themselves_into_a_membership(activation_db):
    _owner(activation_db)
    invitee = _identity(activation_db, "g136-invitee", INVITED_EMAIL)
    result = boot_svc.insert_membership(
        connection=activation_db,
        organization_id=DEMO_ORG,
        identity_id=invitee,
        state="active",
        role="grant_lead",
        membership_source="org_owner_approved",
        approved_by=invitee,
        invited_by=invitee,
        invite_id="nf-invite-g136",
        now=NOW,
    )
    assert result["rows_written"] == 0
    assert "membership_invited_by_the_member_themselves" in result["blocked_reasons"]


def test_an_activation_result_cannot_claim_a_membership_it_did_not_write():
    forged = {
        "membership_activated": True,
        "invite_accepted": True,
        "membership_rows_written": 0,
        "accepter_matched_the_invite": True,
        "is_demo": True,
        "provenance": "completed_invite",
        "blocked_reasons": [],
    }
    fails = activation.activation_invariant_failures(forged)
    assert "membership_activated_without_writing_a_membership" in fails
    assert "invite_accepted_without_a_membership" in fails


def test_an_activation_result_cannot_claim_an_uninvited_accepter():
    forged = {
        "membership_activated": True,
        "invite_accepted": True,
        "membership_rows_written": 1,
        "accepter_matched_the_invite": False,
        "is_demo": True,
        "provenance": "completed_invite",
        "blocked_reasons": [],
    }
    fails = activation.activation_invariant_failures(forged)
    assert "membership_activated_for_somebody_who_was_not_invited" in fails


# ---------------------------------------------------------------------------
# the gate itself
# ---------------------------------------------------------------------------

#: Everything `customer_auth_live` needs, injected. No database. Same shape
#: Gate 135's suite uses, because a second definition of "all the facts" that
#: drifted from the first would make both tests weaker than either.
_PASSING_FACTS = {
    "preflight": {
        "validation_possible": True,
        "client_secret_present": True,
        "issuer_url_present": True,
        "audience_present": True,
        "jwks_reachable": None,
    },
    "route_readiness": {
        "callback_route_available": True,
        "session_cookie_policy_available": True,
    },
    "signing_key_readiness": {"can_sign_production_session": True},
    "binding_evidence": {
        "org_binding_passed": True,
        "callback_session_validated": True,
    },
    "jwks_validation_evidence": {
        "issuer_jwks_validated": True,
        "provider_called": True,
    },
    "role_mapping_evidence": {"role_mapping_passed": True},
    "login_activation_decision": {"approves_login_live": True},
    "invite_binding_evidence": {"invite_binding_passed": True},
    "customer_auth_activation_decision": {"approves_customer_auth_live": True},
    "dev_header_exposure": {"route_total": 217, "dev_header_route_count": 0},
}


def _gate(**overrides):
    facts = {**_PASSING_FACTS, **overrides}
    return build_customer_auth_activation_gate(**facts)


def test_customer_auth_live_becomes_true_with_every_fact_present():
    gate = _gate()
    assert gate["customer_auth_live"] is True
    assert gate["login_live"] is True
    assert gate["missing_auth_gates"] == []
    assert gate["production_rollout"] is False
    assert gate["controlled_customer_pilot"] is False


def test_customer_auth_live_stays_false_without_the_invite():
    gate = _gate(invite_binding_evidence={"invite_binding_passed": False})
    assert gate["customer_auth_live"] is False
    assert "invite_binding_passed" in gate["missing_auth_gates"]
    # The login half is unaffected, which is the point of Gate 133D's split.
    assert gate["login_live"] is True


def test_customer_auth_live_stays_false_without_the_owner_activation():
    gate = _gate(customer_auth_activation_decision={})
    assert gate["customer_auth_live"] is False
    assert gate["owner_approval_source"] == "absent"
    assert (
        "owner_has_not_authorized_customer_auth_activation" in gate["blocked_reasons"]
    )


def test_customer_auth_live_stays_false_when_login_live_is_false():
    """A login gate failing takes customer auth with it.

    Through a *gate* rather than the login decision, and the difference is the
    point of the next test.
    """
    gate = _gate(signing_key_readiness={"can_sign_production_session": False})
    assert gate["login_live"] is False
    assert gate["customer_auth_live"] is False


def test_the_customer_auth_approval_subsumes_the_login_approval():
    """Gate 133D's `or`, asserted rather than tripped over.

    Denying the login decision does not lower `login_live` while the customer
    auth decision approves - approving customer auth approves the login path it
    runs on. Found while writing the test above, which assumed the two
    approvals were independent in both directions. They are independent in one:
    `approves_customer_auth_live` has no branch that returns True, so the
    narrow approval can never stand in for the broad one.
    """
    gate = _gate(login_activation_decision={"approves_login_live": False})
    assert gate["login_live"] is True
    assert gate["customer_auth_live"] is True
    assert gate["owner_approval_source"] == "recorded_decision"

    # And with neither, the login half goes.
    neither = _gate(
        login_activation_decision={"approves_login_live": False},
        customer_auth_activation_decision={},
    )
    assert neither["login_live"] is False
    assert neither["customer_auth_live"] is False


def test_the_owner_decision_still_refuses_the_real_org():
    decision = build_customer_auth_activation_decision(
        organization_id=REAL_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["approves_customer_auth_live"] is False
    assert (
        "organization_is_the_explicitly_refused_real_org" in decision["blocked_reasons"]
    )


# ---------------------------------------------------------------------------
# 136D: the verifier
# ---------------------------------------------------------------------------


class _SessionHandler(BaseHTTPRequestHandler):
    """A stand-in for the backend, serving exactly the two routes read."""

    payload: dict = {}

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's name
        if self.path == "/backend/health":
            body, status = b'{"status":"ok"}', 200
        elif self.path == "/api/auth/session":
            body, status = json.dumps(self.payload).encode(), 200
        elif self.path == "/api/auth/current-user":
            body, status = b'{"error":"unauthenticated"}', 401
        else:
            body, status = b"{}", 404
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):  # keep pytest output clean
        return


@pytest.fixture
def stub_backend():
    def _serve(payload: dict) -> str:
        _SessionHandler.payload = payload
        server = HTTPServer(("127.0.0.1", 0), _SessionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _serve.servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    _serve.servers = []
    yield _serve
    for server in _serve.servers:
        server.shutdown()
        server.server_close()


def _verifier_db(tmp_path: Path, *, completed: bool) -> str:
    """A migrated database, optionally with the whole flow completed in it."""
    url = f"sqlite+pysqlite:///{(tmp_path / 'nf.sqlite3').as_posix()}"
    engine = sa.create_engine(url)
    ORGANIZATIONS.create(engine)
    boot_svc.IDENTITIES.create(engine)
    boot_svc.MEMBERSHIPS.create(engine)
    invite_repo.INVITES.create(engine)
    with engine.begin() as conn:
        for org_id, org_type in ((REAL_ORG, "real"), (DEMO_ORG, "demo")):
            conn.execute(
                sa.insert(ORGANIZATIONS).values(
                    id=uuid.UUID(org_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=NOW,
                )
            )
        owner = _owner(conn)
        if completed:
            invitee = _identity(conn, "g136-invitee", INVITED_EMAIL)
            _issue(conn, owner)
            activation.accept_invite_and_create_membership(
                connection=conn,
                invite_id="nf-invite-g136",
                organization_id=DEMO_ORG,
                accepted_by_identity_id=invitee,
                now=NOW,
            )
    engine.dispose()
    return url


def _run_verifier(backend: str, database_url: str):
    env = dict(os.environ)
    env["NF_BACKEND_OVERRIDE"] = backend
    env["DATABASE_URL"] = database_url
    env["NF_APP_ENV"] = "dev"
    env["OIDC_ISSUER"] = ISSUER
    return subprocess.run(["bash", VERIFIER], capture_output=True, text=True, env=env)


def test_the_verifier_reports_blocked_with_the_exact_blocker(stub_backend, tmp_path):
    """Before the second person completes the flow."""
    backend = stub_backend(
        {
            "login_live": True,
            "customer_auth_live": False,
            "blocked_reasons": ["auth_gate_not_satisfied:invite_binding_passed"],
        }
    )
    proc = _run_verifier(backend, _verifier_db(tmp_path, completed=False))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RESULT=BLOCKED" in proc.stdout
    assert "customer_auth_live=false" in proc.stdout
    assert "blocker=invite_binding_passed" in proc.stdout
    assert "check=login_live status=PASS" in proc.stdout
    assert "check=dev_header_consumers_zero status=PASS n=0" in proc.stdout
    assert "count=invite_rows n=0" in proc.stdout


def test_the_verifier_can_report_pass(stub_backend, tmp_path):
    """RESULT=PASS is reachable, which is what makes every BLOCKED meaningful.

    The database has a genuinely completed invite in it, written by the same
    service the operator script calls. Nothing is asserted into the gate.
    """
    backend = stub_backend(
        {"login_live": True, "customer_auth_live": True, "blocked_reasons": []}
    )
    proc = _run_verifier(backend, _verifier_db(tmp_path, completed=True))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT=PASS" in proc.stdout
    assert "customer_auth_live=true" in proc.stdout
    assert "production_rollout=false" in proc.stdout
    assert "controlled_customer_pilot=false" in proc.stdout
    assert "check=invite_binding_passed status=PASS" in proc.stdout
    assert "count=memberships_from_a_completed_invite n=1" in proc.stdout


def test_the_verifier_refuses_to_agree_when_the_gate_and_the_rows_disagree(
    stub_backend, tmp_path
):
    """A gate claiming live over an empty invite table is worse than a blocker.

    One of the two is wrong, and this script will not pick which.
    """
    backend = stub_backend(
        {"login_live": True, "customer_auth_live": True, "blocked_reasons": []}
    )
    proc = _run_verifier(backend, _verifier_db(tmp_path, completed=False))
    assert proc.returncode == 1
    assert "RESULT=BLOCKED" in proc.stdout
    assert "gate_says_live_while_measurements_say" in proc.stdout


def test_the_verifier_prints_nothing_secret(stub_backend, tmp_path):
    backend = stub_backend(
        {"login_live": True, "customer_auth_live": True, "blocked_reasons": []}
    )
    proc = _run_verifier(backend, _verifier_db(tmp_path, completed=True))
    combined = (proc.stdout + proc.stderr).lower()
    for forbidden in (
        INVITED_EMAIL,
        OWNER_EMAIL,
        "example.test",
        "set-cookie",
        "id_token",
        "access_token",
        "code_verifier",
    ):
        assert forbidden.lower() not in combined, forbidden


# ---------------------------------------------------------------------------
# 136F: artifacts
# ---------------------------------------------------------------------------


def test_the_artifacts_exist_and_carry_no_secrets():
    from nativeforge.services import invite_activation_artifact_gate136_service as art

    result = art.build_activation_artifacts()
    assert set(result) == set(art.ARTIFACT_FILES)
    blob = "\n".join(result.values()).lower()

    # Values, which have no honest reason to be here.
    for forbidden in ("example.test", "gocspx-", "set-cookie:", "eyj"):
        assert forbidden not in blob, forbidden

    # And credential FIELDS only when they carry something. `"id_token"` inside
    # `what_the_row_refuses` is the safeguard being documented, and the first
    # version of this assertion failed on exactly that - the eleventh
    # substring-for-meaning slip in this campaign, this one mine.
    import re

    for field in art.CREDENTIAL_FIELDS:
        assert not re.search(rf'"{re.escape(field)}"\s*:\s*"', blob), field
        assert not re.search(rf"\b{re.escape(field)}\s*=\s*\S", blob), field

    # The refusal list is present, which is what makes the discrimination
    # necessary rather than convenient.
    assert '"id_token"' in blob


def test_the_artifacts_regenerate_deterministically(tmp_path):
    from nativeforge.services import invite_activation_artifact_gate136_service as art

    art.write_activation_artifacts(repo_root=tmp_path)
    written = {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / art.ARTIFACT_DIR).iterdir()
    }
    again = art.build_activation_artifacts()
    for name, body in written.items():
        assert body == again[name], name

    committed = Path(art.ARTIFACT_DIR)
    for name, body in written.items():
        assert (committed / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_do_not_claim_customer_auth_is_live():
    from nativeforge.services import invite_activation_artifact_gate136_service as art

    files = art.build_activation_artifacts()
    status = json.loads(files["invite_activation_readiness.json"])
    assert status["customer_auth_live"] is False
    assert status["production_rollout"] is False
    assert status["controlled_customer_pilot"] is False
    assert status["fake_users_created"] == 0
    assert status["email_sent"] is False


# ---------------------------------------------------------------------------
# 136E: the execution guide is not theoretical
# ---------------------------------------------------------------------------


def test_the_execution_guide_names_the_commands_that_exist():
    guide = Path(
        "docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md"
    ).read_text(encoding="utf-8")
    for script in (ISSUE_SCRIPT, ACCEPT_SCRIPT, VERIFIER):
        assert script in guide, script
        assert Path(script).exists(), script
    assert DEMO_ORG in guide
    assert "https://nf-dev.mayhem-nc.dev" in guide
    # The step nothing in this repository can do.
    assert "test user" in guide.lower()


def test_the_execution_guide_carries_no_address():
    guide = Path(
        "docs/operations/717_GATE136_SECOND_ACCOUNT_INVITE_EXECUTION.md"
    ).read_text(encoding="utf-8")
    assert "@gmail.com" not in guide
    assert "example.test" not in guide
