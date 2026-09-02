"""Gate 135: the invite seam, the owner decision, and the chains that went.

Two blockers stood between NativeForge and `customer_auth_live`. One was a
decision and Mayhem made it. The other needs a second person to accept an
invite, and this file proves the path works while refusing to pretend somebody
walked it.

The tests are grouped by what they would catch:

```text
removal      a deleted chain still reachable, or the header authorizing anything
invite       a binding claimed without an invite anybody accepted
scope        a login approval reaching customer auth, or demo reaching production
gate         customer_auth_live true on anything less than all of it
artifacts    a secret reaching a file, or a file that will not regenerate
```
"""

from __future__ import annotations

import ast
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import (
    customer_auth_activation_artifact_gate135_service as art,
)
from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import (
    customer_auth_owner_activation_decision_service as owner_svc,
)
from nativeforge.services import dev_header_exposure_matrix_service as matrix_svc
from nativeforge.services import dev_org_header_shutdown_readiness_service as shutdown
from nativeforge.services import dev_org_membership_bootstrap_service as boot_svc
from nativeforge.services import membership_invite_repository_service as invite_repo

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"
NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

_ORG_META = sa.MetaData()
ORGANIZATIONS = sa.Table(
    "organizations",
    _ORG_META,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


@pytest.fixture
def invite_db():
    """Organizations, identities, memberships and invites, for one test."""
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


def _identity(conn, subject: str) -> str:
    return boot_svc.upsert_identity(
        connection=conn,
        issuer=ISSUER,
        subject=subject,
        email_verified=True,
        verification_source="oidc_token_signature",
        now=NOW,
    )["identity_id"]


def _owner(conn) -> str:
    identity_id = _identity(conn, "gate135-owner")
    boot_svc.insert_membership(
        connection=conn,
        organization_id=DEMO_ORG,
        identity_id=identity_id,
        state="active",
        role="org_owner",
        membership_source="verified_directory",
        approved_by=None,
        now=NOW,
    )
    return identity_id


def _invite_fields(owner: str, invite_id: str = "nf-invite-1", **overrides):
    fields = {
        "invite_id": invite_id,
        "requested_role": "grant_lead",
        "requested_by": owner,
        "requested_by_role": "org_owner",
        "invited_email": "invitee@example.test",
        "invite_state": "approved",
        "approval_required": True,
        "approval_state": "approved",
        "approved_by": owner,
        "approved_by_role": "org_owner",
        "seat_cap": 5,
        "seat_count": 1,
        "expires_at": "2026-12-31T00:00:00+00:00",
        "now": "2026-09-02T00:00:00+00:00",
    }
    fields.update(overrides)
    return fields


# ---------------------------------------------------------------------------
# removal: the chains Gate 134 made obsolete
# ---------------------------------------------------------------------------


def test_the_dead_chains_are_gone():
    """Deleted, not merely unused."""
    api = Path("src/nativeforge/api")
    assert not (api / "isolation_deps.py").exists()

    deps_db = (api / "deps_db.py").read_text(encoding="utf-8")
    tree = ast.parse(deps_db)
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert defined == {"get_db_session"}

    deps_customer_auth = (api / "deps_customer_auth.py").read_text(encoding="utf-8")
    names = {
        node.name
        for node in ast.parse(deps_customer_auth).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    assert "get_dev_org_context_explicit_only" not in names


def test_nothing_declares_the_dev_header_any_more():
    """A `Header(alias=...)` is the only way it could arrive."""
    found: list[str] = []
    for path in sorted(Path("src/nativeforge").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for keyword in getattr(node, "keywords", []):
                if (
                    keyword.arg == "alias"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == matrix_svc.DEV_HEADER_NAME
                ):
                    found.append(str(path))
    assert found == []


def test_no_route_consumes_the_dev_header():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    assert matrix["dev_header_route_count"] == 0
    assert matrix["dev_header_modules"] == []
    assert matrix_svc.matrix_invariant_failures(matrix) == []


def test_the_detector_reports_no_providers_left():
    """The chains were the providers. With them gone there are none."""
    readiness = shutdown.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_used_by_routes"] == 0
    assert readiness["dev_header_provider_modules"] == []
    # What remains names the header in prose - `auth.py` explaining why it does
    # not use one, and the replacement explaining what it replaced.
    assert set(readiness["dev_header_mention_only_modules"]) <= {
        "auth.py",
        "capability_guard.py",
        "customer_org_context_dependency.py",
        "deps_customer_auth.py",
        "deps_db.py",
    }
    assert shutdown.shutdown_readiness_invariant_failures(readiness) == []


def test_a_returning_consumer_would_still_be_counted():
    """The zero is measured, so it can go back up."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / "regressed_routes.py"
        module.write_text(
            "from nativeforge.api.deps_db import require_real_org_db\n"
            "def x(ctx=Depends(require_real_org_db)):\n"
            "    return {}\n",
            encoding="utf-8",
        )
        usage = shutdown.detect_dev_header_route_usage(Path(tmp))
    assert usage["module_count"] == 1


# ---------------------------------------------------------------------------
# invite: what a binding requires
# ---------------------------------------------------------------------------


def test_an_invite_is_recorded_without_the_address_or_the_subject(invite_db):
    owner = _owner(invite_db)
    result = invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner, invited_subject="a-real-provider-subject"),
    )
    assert result["rows_written"] == 1
    assert result["email_sent"] is False

    record = result["record"]
    assert record["invited_email_domain"] == "example.test"
    assert record["invited_subject_fingerprint"]
    blob = json.dumps(record)
    assert "invitee@example.test" not in blob
    assert "a-real-provider-subject" not in blob
    assert invite_repo.invite_record_invariant_failures(result) == []


def test_an_approved_invite_nobody_accepted_binds_nobody(invite_db):
    owner = _owner(invite_db)
    invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner),
    )
    evidence = invite_repo.build_invite_binding_evidence(connection=invite_db)
    assert evidence["approved_invite_rows"] == 1
    assert evidence["accepted_invite_rows"] == 0
    assert evidence["invite_binding_passed"] is False
    assert "no_invite_has_been_accepted_by_an_identity" in evidence["blocked_reasons"]
    assert invite_repo.invite_evidence_invariant_failures(evidence) == []


def test_the_owner_cannot_accept_their_own_invite(invite_db):
    """The contract exists because somebody else has to say yes.

    `evaluate_invite` does not catch this - every seat and role check passes
    when one person plays all three parts - so the repository does.
    """
    owner = _owner(invite_db)
    invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner),
    )
    result = invite_repo.record_acceptance(
        connection=invite_db,
        invite_id="nf-invite-1",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=owner,
    )
    assert result["accepted"] is False
    assert invite_repo.SELF_DEALT in result["blocked_reasons"]


def test_an_invite_cannot_be_accepted_by_an_identity_that_does_not_exist(invite_db):
    """The guard against the shape of a faked user."""
    owner = _owner(invite_db)
    invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner),
    )
    result = invite_repo.record_acceptance(
        connection=invite_db,
        invite_id="nf-invite-1",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=str(uuid.uuid4()),
    )
    assert result["accepted"] is False
    assert "accepting_identity_does_not_exist" in result["blocked_reasons"]


def test_a_self_dealt_invite_is_refused_at_write_time(invite_db):
    owner = _owner(invite_db)
    result = invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        accepted_by_identity_id=owner,
        **_invite_fields(owner, invite_state="accepted"),
    )
    assert result["rows_written"] == 0
    assert result["self_dealt"] is True
    assert invite_repo.SELF_DEALT in result["blocked_reasons"]


def test_an_accepted_invite_alone_still_binds_nobody(invite_db):
    """Acceptance is not a membership."""
    owner = _owner(invite_db)
    invitee = _identity(invite_db, "gate135-invitee")
    invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner),
    )
    accepted = invite_repo.record_acceptance(
        connection=invite_db,
        invite_id="nf-invite-1",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    assert accepted["accepted"] is True

    evidence = invite_repo.build_invite_binding_evidence(connection=invite_db)
    assert evidence["accepted_invite_rows"] == 1
    assert evidence["memberships_from_a_completed_invite"] == 0
    assert evidence["invite_binding_passed"] is False
    assert (
        "no_active_membership_came_through_a_completed_invite"
        in evidence["blocked_reasons"]
    )


def test_the_completed_branch_is_reachable(invite_db):
    """Otherwise every refusal above is unfalsifiable.

    An invite issued by an owner, accepted by a second identity, producing a
    membership that identity holds. This is the state the demo organization
    cannot reach without a second real person.
    """
    owner = _owner(invite_db)
    invitee = _identity(invite_db, "gate135-invitee")
    invite_repo.insert_invite(
        connection=invite_db,
        organization_id=DEMO_ORG,
        created_at=NOW,
        **_invite_fields(owner),
    )
    invite_repo.record_acceptance(
        connection=invite_db,
        invite_id="nf-invite-1",
        organization_id=DEMO_ORG,
        accepted_by_identity_id=invitee,
        now=NOW,
    )
    boot_svc.insert_membership(
        connection=invite_db,
        organization_id=DEMO_ORG,
        identity_id=invitee,
        state="active",
        role="grant_lead",
        membership_source="org_owner_approved",
        approved_by=owner,
        now=NOW,
    )

    evidence = invite_repo.build_invite_binding_evidence(connection=invite_db)
    assert evidence["invite_binding_passed"] is True
    assert evidence["memberships_from_a_completed_invite"] == 1
    assert evidence["blocked_reasons"] == []
    assert invite_repo.invite_evidence_invariant_failures(evidence) == []


def test_a_demo_fixture_binding_alone_does_not_satisfy_the_invite_gate(invite_db):
    """The demo organization has a binding and it is not an invite.

    Gate 132 wrote a `demo_fixture` binding for this organization. It proves a
    tenant label maps to an organization; it says nothing about how anybody came
    to be a member.
    """
    _owner(invite_db)
    evidence = invite_repo.build_invite_binding_evidence(connection=invite_db)
    assert evidence["membership_rows"] == 1
    assert evidence["invite_binding_passed"] is False
    assert "no_invite_has_been_recorded" in evidence["blocked_reasons"]


def test_no_evidence_without_a_connection():
    evidence = invite_repo.build_invite_binding_evidence()
    assert evidence["invite_binding_passed"] is False
    assert evidence["blocked_reasons"] == ["no_connection_supplied"]


def test_a_forged_evidence_result_fires_the_invariant():
    forged = {
        "connection_supplied": True,
        "invite_rows": 1,
        "accepted_invite_rows": 0,
        "membership_rows": 1,
        "memberships_from_a_completed_invite": 0,
        "invite_binding_passed": True,
    }
    fails = invite_repo.invite_evidence_invariant_failures(forged)
    assert "invite_binding_passed_without_an_accepted_invite" in fails
    assert "invite_binding_passed_without_a_membership_from_one" in fails


def test_the_invite_vocabulary_matches_the_migration():
    """A restated constant drifting from its CHECK is this campaign's shape."""
    source = Path("alembic/versions/0038_nf_membership_invites.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"INVITE_STATES", "APPROVAL_STATES"}:
                found[name] = set(ast.literal_eval(node.value))

    from nativeforge.services.membership_invite_approval_service import (
        APPROVAL_STATES,
        INVITE_STATES,
    )

    assert found["INVITE_STATES"] == set(INVITE_STATES)
    assert found["APPROVAL_STATES"] == set(APPROVAL_STATES)

    for column in invite_repo.INVITES.columns:
        assert f'"{column.name}"' in source, column.name


# ---------------------------------------------------------------------------
# scope: which decision approves what
# ---------------------------------------------------------------------------


def test_the_login_approval_is_not_a_customer_auth_approval():
    """Gate 133D split them; this is the half that must not creep."""
    login = owner_svc.build_owner_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    assert login["approves_login_live"] is True
    assert login["approves_customer_auth_live"] is False
    assert owner_svc.approves_customer_auth_live() is False


def test_the_customer_auth_approval_is_demo_scoped():
    decision = owner_svc.build_customer_auth_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["approves_customer_auth_live"] is True
    assert decision["organization_in_scope"] is True
    assert decision["blocked_reasons"] == []
    assert owner_svc.customer_auth_decision_invariant_failures(decision) == []


def test_the_customer_auth_approval_refuses_the_real_organization():
    decision = owner_svc.build_customer_auth_activation_decision(
        organization_id=REAL_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["approves_customer_auth_live"] is False
    assert (
        "organization_is_the_explicitly_refused_real_org" in decision["blocked_reasons"]
    )


@pytest.mark.parametrize("environment", ["production", "prod", "", "staging"])
def test_the_customer_auth_approval_refuses_production(environment):
    decision = owner_svc.build_customer_auth_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env=environment
    )
    assert decision["approves_customer_auth_live"] is False
    assert any(
        reason.startswith("environment_outside_the_approved_scope")
        for reason in decision["blocked_reasons"]
    )


def test_the_customer_auth_approval_never_approves_rollout_or_a_pilot():
    """No parameter reaches either, in any environment."""
    for environment in ("dev", "local", "test", "production"):
        decision = owner_svc.build_customer_auth_activation_decision(
            organization_id=DEMO_ORG, provider=ISSUER, app_env=environment
        )
        assert decision["approves_production_rollout"] is False
        assert decision["approves_controlled_customer_pilot"] is False

    forged = dict(
        owner_svc.build_customer_auth_activation_decision(
            organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
        )
    )
    forged["approves_production_rollout"] = True
    assert (
        "decision_approved_production_rollout"
        in owner_svc.customer_auth_decision_invariant_failures(forged)
    )


def test_the_customer_auth_approval_is_revocable(monkeypatch):
    monkeypatch.setenv(owner_svc.CUSTOMER_AUTH_REVOCATION_ENV, "true")
    decision = owner_svc.build_customer_auth_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["revoked"] is True
    assert decision["approves_customer_auth_live"] is False


# ---------------------------------------------------------------------------
# gate: customer_auth_live needs all of it
# ---------------------------------------------------------------------------


def _all_facts(**overrides):
    """Everything `customer_auth_live` needs, injected. No database."""
    facts = {
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
    facts.update(overrides)
    return gate_svc.build_customer_auth_activation_gate(**facts)


def test_customer_auth_live_becomes_true_only_with_all_of_it():
    gate = _all_facts()
    assert gate["customer_auth_live"] is True
    assert gate["login_live"] is True
    assert gate["missing_auth_gates"] == []
    assert gate["owner_approval_source"] == "recorded_decision"
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_customer_auth_live_is_false_without_the_invite():
    gate = _all_facts(invite_binding_evidence={})
    assert gate["customer_auth_live"] is False
    assert "invite_binding_passed" in gate["missing_auth_gates"]
    # And the login half is unaffected, which is the point of the split.
    assert gate["login_live"] is True


def test_customer_auth_live_is_false_without_the_owner_decision():
    gate = _all_facts(customer_auth_activation_decision={})
    assert gate["customer_auth_live"] is False
    assert gate["owner_approval_source"] == "absent"
    assert (
        "owner_has_not_authorized_customer_auth_activation" in gate["blocked_reasons"]
    )


def test_customer_auth_live_is_false_while_a_dev_header_consumer_remains():
    gate = _all_facts(
        dev_header_exposure={"route_total": 217, "dev_header_route_count": 3}
    )
    assert gate["customer_auth_live"] is False
    assert "dev_header_disabled_for_production" in gate["missing_auth_gates"]


def test_customer_auth_live_is_false_without_the_session_proof():
    """`org_binding_passed` is what a session and a membership prove."""
    gate = _all_facts(binding_evidence={})
    assert gate["customer_auth_live"] is False
    assert "org_binding_passed" in gate["missing_auth_gates"]
    assert "callback_session_validated" in gate["missing_auth_gates"]


def test_production_rollout_stays_false_when_customer_auth_is_live():
    gate = _all_facts()
    assert gate["customer_auth_live"] is True
    assert gate["production_rollout"] is False
    assert gate["controlled_customer_pilot"] is False

    forged = dict(gate)
    forged["production_rollout"] = True
    assert (
        "activation_gate_claimed:production_rollout"
        in gate_svc.activation_gate_invariant_failures(forged)
    )


def test_the_deterministic_gate_claims_nothing():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["customer_auth_live"] is False
    assert gate["invite_binding_passed"] is False
    assert gate["production_rollout"] is False
    assert gate["controlled_customer_pilot"] is False


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_set_is_the_one_the_gate_asked_for():
    files = art.build_activation_artifacts(repo_root=".")
    assert set(files) == set(art.ARTIFACT_FILES)
    assert len(art.ARTIFACT_FILES) == 7


def test_artifacts_regenerate_deterministically():
    first = art.build_activation_artifacts(repo_root=".")
    second = art.build_activation_artifacts(repo_root=".")
    assert first == second


def test_artifacts_carry_no_token_cookie_state_or_secret(tmp_path):
    result = art.write_activation_artifacts(repo_root=tmp_path)
    assert result["file_count"] == 7
    assert result["marker_hits"] == []
    assert result["env_value_hits"] == []
    assert result["email_sent"] is False
    assert art.activation_artifact_invariant_failures(result) == []


def test_the_artifact_scan_would_catch_an_environment_value(monkeypatch, tmp_path):
    marker = "nf-gate135-scanner-probe-value"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", marker)

    original = art.build_activation_artifacts

    def _leaky(**kwargs):
        files = dict(original(**kwargs))
        files["invite_binding_evidence.json"] = json.dumps({"oops": marker})
        return files

    monkeypatch.setattr(art, "build_activation_artifacts", _leaky)
    result = art.write_activation_artifacts(repo_root=tmp_path)
    assert result["env_value_hits"] == [
        "invite_binding_evidence.json:OIDC_CLIENT_SECRET"
    ]
    assert (
        "environment_value_reached_an_artifact"
        in art.activation_artifact_invariant_failures(result)
    )


def test_no_artifact_carries_an_email_address(tmp_path):
    import re

    art.write_activation_artifacts(repo_root=tmp_path)
    out = tmp_path / art.ARTIFACT_DIR
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for name in art.ARTIFACT_FILES:
        assert email.search((out / name).read_text(encoding="utf-8")) is None, name


def test_the_artifacts_do_not_claim_customer_auth_is_live(tmp_path):
    art.write_activation_artifacts(repo_root=tmp_path)
    payload = json.loads(
        (
            tmp_path / art.ARTIFACT_DIR / "customer_auth_readiness_after_gate135.json"
        ).read_text(encoding="utf-8")
    )
    unmoved = payload["flags_this_gate_did_not_move"]
    assert unmoved == dict.fromkeys(unmoved, False)
    assert payload["measured_against_the_dev_deployment"]["customer_auth_live"] is False
    assert payload["measured_against_the_dev_deployment"]["login_live"] is True


def test_the_recorded_smoke_names_the_single_blocker():
    assert art.LIVE_SMOKE["login_live"] is True
    assert art.LIVE_SMOKE["customer_auth_live"] is False
    assert art.LIVE_SMOKE["blocked_reasons"] == [
        "auth_gate_not_satisfied:invite_binding_passed"
    ]
    assert art.LIVE_INVITE_EVIDENCE["invite_binding_passed"] is False
