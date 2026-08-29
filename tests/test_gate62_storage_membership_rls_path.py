"""Tests: Gate 62 storage / membership / RLS path (completed in Gate 64).

Gate 62 was interrupted before this file was written, so the RLS proof it did
achieve had no repeatable coverage. These tests cover the two artifacts that
close it: the ``verify_nativeforge_postgres_rls.sh`` harness and
``PostgresMembershipDirectory``.

The thing under test is mostly *refusal*. Almost every assertion here checks
that some plausible-looking input does **not** produce authority, because the
failure mode that matters is a claim being true-ish rather than true.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from nativeforge.services.postgres_membership_directory_service import (
    EXPECTED_MIGRATION_HEAD,
    PostgresMembershipDirectory,
    postgres_storage_status,
    resolution_invariant_failures,
    resolve_persisted_membership,
    storage_status_invariant_failures,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_nativeforge_postgres_rls.sh"

ALL_PRECONDITIONS = {
    "approval_token_present": True,
    "database_url_present": True,
    "migrations_at_expected_head": True,
    "rls_proof_passed": True,
    "backup_restore_posture_documented": True,
}

VERIFIED_IDENTITY = {
    "verification_trusted": True,
    "issuer": "https://example-tenant.us.auth0.com/",
    "subject": "auth0|abc123",
    "email": "person@example.org",
}

IDENTITY_ROW = {
    "id": "id-row-1",
    "issuer": VERIFIED_IDENTITY["issuer"],
    "subject": VERIFIED_IDENTITY["subject"],
    "email": VERIFIED_IDENTITY["email"],
    "email_verified": True,
}

# Gate 113: a real organization_id. This was "org-profile-1" - a
# profile-shaped string flowing into the organization_id UUID predicate,
# which is exactly the conflation Gate 113 fixed. The lookup now refuses a
# non-UUID value, so these tests supply the identity the column holds.
ORG = "00000000-0000-4000-8000-0000000000a1"


def _membership_row(**overrides: object) -> dict[str, object]:
    row = {
        "id": "mem-1",
        "organization_id": ORG,
        "identity_id": "id-row-1",
        "state": "active",
        "membership_source": "org_owner_approved",
        "role": "grant_lead",
        "role_source": "membership_record",
        "approved_by": "owner-1",
        "revoked_at": None,
        "expires_at": None,
    }
    row.update(overrides)
    return row


def _directory(
    *,
    identity_row: dict[str, object] | None = None,
    membership_row: dict[str, object] | None = None,
    **posture: bool,
) -> PostgresMembershipDirectory:
    """A directory backed by a stub row source.

    The stub answers by table name rather than by parsing SQL — the point is to
    exercise the trust logic, not to re-test the database.
    """

    def row_source(sql: str, params: dict[str, object]):
        if "nf_identities" in sql:
            if identity_row is None:
                return ()
            if params.get("issuer") != identity_row.get("issuer") or params.get(
                "subject"
            ) != identity_row.get("subject"):
                return ()
            return (identity_row,)
        if "nf_org_memberships" in sql:
            if membership_row is None:
                return ()
            return (membership_row,)
        return ()

    merged = {"database_url_present": True, **posture}
    return PostgresMembershipDirectory(row_source, **merged)


# ── storage-live gating ─────────────────────────────────────────────────────


def test_no_database_url_does_not_claim_production_storage_live() -> None:
    status = postgres_storage_status()
    assert status["production_storage_live"] is False
    assert status["customer_persistence_claimed"] is False
    assert "database_url_present" in status["missing_preconditions"]
    assert not storage_status_invariant_failures(status)


def test_approval_token_alone_does_not_claim_production_storage_live() -> None:
    """The approval Mayhem gave in Gate 61 authorises building. It is not proof."""
    status = postgres_storage_status(approval_token_present=True)
    assert status["production_storage_live"] is False
    assert "database_url_present" in status["missing_preconditions"]


def test_database_url_alone_does_not_claim_production_storage_live() -> None:
    status = postgres_storage_status(database_url_present=True)
    assert status["production_storage_live"] is False
    assert "approval_token_present" in status["missing_preconditions"]
    assert "rls_proof_passed" in status["missing_preconditions"]


@pytest.mark.parametrize("dropped", sorted(ALL_PRECONDITIONS))
def test_every_precondition_is_individually_load_bearing(dropped: str) -> None:
    """Removing any one of the five must be enough to keep the claim false."""
    posture = dict(ALL_PRECONDITIONS)
    posture[dropped] = False
    status = postgres_storage_status(**posture)
    assert status["production_storage_live"] is False
    assert status["missing_preconditions"] == [dropped]


def test_all_preconditions_together_permit_the_claim() -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    status = postgres_storage_status(**ALL_PRECONDITIONS)
    assert status["production_storage_live"] is True
    assert status["missing_preconditions"] == []
    # Still not persistence, and still not login.
    assert status["customer_persistence_claimed"] is False
    assert status["customer_login_live"] is False
    assert not storage_status_invariant_failures(status)


def test_persistence_needs_live_storage_and_a_proof_artifact() -> None:
    without_storage = postgres_storage_status(
        persistence_proof_artifact="artifacts/restore/whatever.json"
    )
    assert without_storage["customer_persistence_claimed"] is False

    with_both = postgres_storage_status(
        **ALL_PRECONDITIONS,
        persistence_proof_artifact="artifacts/restore/whatever.json",
    )
    assert with_both["customer_persistence_claimed"] is True
    assert not storage_status_invariant_failures(with_both)


def test_invariants_reject_a_forged_live_status() -> None:
    forged = postgres_storage_status()
    forged["production_storage_live"] = True
    fails = storage_status_invariant_failures(forged)
    assert "production_live_without:database_url_present" in fails
    assert "production_live_without:rls_proof_passed" in fails


def test_expected_migration_head_matches_gate63_doctrine() -> None:
    """One head constant per repo. Drift here would silently un-pin the adapter."""
    doctrine = (ROOT / "tests" / "test_gate63_migration_doctrine.py").read_text(
        encoding="utf-8"
    )
    assert f'CURRENT_HEAD = "{EXPECTED_MIGRATION_HEAD}"' in doctrine


# ── the verify script ───────────────────────────────────────────────────────


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,  # deliberately no DATABASE_URL
    )


def test_verify_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111, "script must be executable"


def test_dry_run_needs_no_credentials() -> None:
    r = _run("--dry-run")
    assert r.returncode == 0
    assert "RESULT=FAIL" not in r.stdout
    assert "check=dry_run_mode status=PASS" in r.stdout
    # The reason for any skip must be explained, not silent.
    assert "check=database_url_present status=SKIP" in r.stdout
    assert "unset" in r.stdout


def test_dry_run_proves_its_own_redaction() -> None:
    """The redaction routine is the credential control, so it self-tests."""
    r = _run("--dry-run")
    assert "check=redaction_self_test status=PASS" in r.stdout
    assert "hunter2" not in r.stdout, "the sample password leaked into output"
    assert "***" in r.stdout
    assert "check=redaction_passwordless_url status=PASS" in r.stdout


def test_check_config_skips_without_database_url() -> None:
    r = _run("--check-config")
    assert r.returncode == 0
    assert "RESULT=SKIP" in r.stdout
    assert "check=database_url_present status=SKIP" in r.stdout


def test_verify_rls_skips_without_database_url() -> None:
    r = _run("--verify-rls")
    assert r.returncode == 0
    assert "RESULT=SKIP" in r.stdout


def test_strict_fails_without_database_url() -> None:
    """The whole point of --strict: absence stops being an acceptable answer."""
    r = _run("--strict")
    assert r.returncode == 1
    assert "RESULT=FAIL" in r.stdout
    assert "check=database_url_present status=FAIL" in r.stdout


def test_no_mode_defaults_to_dry_run_not_to_a_live_proof() -> None:
    r = _run()
    assert "verify_mode=dry-run" in r.stdout
    assert r.returncode == 0


def test_unknown_argument_is_rejected_rather_than_ignored() -> None:
    r = _run("--verify-everything")
    assert r.returncode == 2
    assert "RESULT=FAIL" in r.stdout


def test_script_never_echoes_the_raw_database_url_variable() -> None:
    """A grep-level guard against the one mistake that cannot be walked back."""
    body = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ('echo "$DATABASE_URL"', "echo $DATABASE_URL"):
        assert forbidden not in body
    assert 'say database_url_redacted PASS "${REDACTED}"' in body


def test_script_declares_every_required_check_name() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    for name in (
        "database_url_present",
        "database_url_redacted",
        "postgres_dialect",
        "app_role_not_superuser",
        "app_role_not_table_owner",
        "rls_enabled",
        "rls_forced",
        "same_org_read_allowed",
        "cross_org_read_blocked",
        "unscoped_read_blocked",
        "membership_cross_org_read_blocked",
        "membership_cross_org_write_blocked",
        "result",
    ):
        assert f"say {name} " in body, f"missing check: {name}"


# ── the adapter: failing closed ─────────────────────────────────────────────


def test_adapter_fails_closed_without_a_row_source() -> None:
    directory = PostgresMembershipDirectory()
    assert directory.configured is False
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert "no_production_storage_configured" in result["blocked_reasons"]
    assert result["trusted_role"] is None
    assert result["audit_event"]["persisted"] is False
    assert not resolution_invariant_failures(result)


def test_adapter_fails_closed_with_no_directory_at_all() -> None:
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=None
    )
    assert result["allowed"] is False
    assert result["production_storage_live"] is False


def test_row_source_without_database_url_is_still_unconfigured() -> None:
    """A stub wired up in a test must not look like a provisioned database."""
    directory = PostgresMembershipDirectory(
        lambda sql, params: (), database_url_present=False
    )
    assert directory.configured is False


# ── the adapter: identity and membership ────────────────────────────────────


def test_verified_identity_alone_cannot_act_without_membership() -> None:
    """Gate 60 ends at a verified token. A token is not a seat."""
    directory = _directory(identity_row=IDENTITY_ROW, membership_row=None)
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert result["identity_row_found"] is True
    assert "no_membership_row" in result["blocked_reasons"]
    assert result["trusted_role"] is None


def test_unverified_identity_is_denied_even_with_a_perfect_membership() -> None:
    directory = _directory(identity_row=IDENTITY_ROW, membership_row=_membership_row())
    result = resolve_persisted_membership(
        identity={**VERIFIED_IDENTITY, "verification_trusted": False},
        organization_id=ORG,
        directory=directory,
    )
    assert result["allowed"] is False
    assert "identity_verification_not_trusted" in result["blocked_reasons"]


def test_active_trusted_membership_maps_a_role_in_the_modeled_path() -> None:
    directory = _directory(identity_row=IDENTITY_ROW, membership_row=_membership_row())
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is True, result["blocked_reasons"]
    assert result["trusted_role"] == "grant_lead"
    assert result["membership_state"] == "active"
    # Allowed to act, and still not a production claim.
    assert result["production_storage_live"] is False
    assert result["customer_persistence_claimed"] is False
    assert result["customer_login_live"] is False
    assert not resolution_invariant_failures(result)


def test_identity_is_keyed_on_issuer_and_subject_not_email() -> None:
    """Same subject string, different issuer, must not resolve."""
    directory = _directory(identity_row=IDENTITY_ROW, membership_row=_membership_row())
    result = resolve_persisted_membership(
        identity={**VERIFIED_IDENTITY, "issuer": "https://evil.example/"},
        organization_id=ORG,
        directory=directory,
    )
    assert result["allowed"] is False
    assert "no_identity_row" in result["blocked_reasons"]


# ── the adapter: denial rules ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "state", ["revoked", "suspended", "expired", "invited", "pending"]
)
def test_non_active_membership_states_deny(state: str) -> None:
    directory = _directory(
        identity_row=IDENTITY_ROW, membership_row=_membership_row(state=state)
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert result["trusted_role"] is None
    assert any(
        r.startswith("membership_state_denies") for r in result["blocked_reasons"]
    )


def test_revocation_timestamp_overrides_an_active_state_column() -> None:
    """A row claiming active while carrying revoked_at is revoked."""
    directory = _directory(
        identity_row=IDENTITY_ROW,
        membership_row=_membership_row(
            state="active", revoked_at="2026-01-01T00:00:00Z"
        ),
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert result["membership_state"] == "revoked"


def test_expiry_is_evaluated_against_caller_supplied_now() -> None:
    row = _membership_row(state="active", expires_at="2026-06-01T00:00:00Z")
    directory = _directory(identity_row=IDENTITY_ROW, membership_row=row)

    before = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY,
        organization_id=ORG,
        directory=directory,
        now="2026-05-01T00:00:00Z",
    )
    assert before["allowed"] is True, before["blocked_reasons"]

    after = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY,
        organization_id=ORG,
        directory=directory,
        now="2026-07-01T00:00:00Z",
    )
    assert after["allowed"] is False
    assert after["membership_state"] == "expired"


@pytest.mark.parametrize(
    "source", ["cloudflare_access", "client_header", "dev_header", "email_domain_only"]
)
def test_untrusted_membership_sources_deny(source: str) -> None:
    """Cloudflare Access protects the demo. It never becomes customer membership."""
    directory = _directory(
        identity_row=IDENTITY_ROW,
        membership_row=_membership_row(membership_source=source),
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert result["trusted_role"] is None
    assert any(
        r.startswith("membership_source_never_trusted")
        for r in result["blocked_reasons"]
    )


@pytest.mark.parametrize(
    "source", ["token_claim", "client_header", "email_domain", "none"]
)
def test_untrusted_role_sources_deny(source: str) -> None:
    """An IdP group claim is the provider's opinion, not this product's record."""
    directory = _directory(
        identity_row=IDENTITY_ROW, membership_row=_membership_row(role_source=source)
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert any(
        r.startswith("role_source_not_trusted") for r in result["blocked_reasons"]
    )


def test_internal_role_cannot_become_customer_authority() -> None:
    directory = _directory(
        identity_row=IDENTITY_ROW,
        membership_row=_membership_row(role="operator_internal"),
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert "internal_role_cannot_hold_customer_authority" in result["blocked_reasons"]


def test_unknown_role_grants_nothing() -> None:
    """`unknown` is a valid vocabulary value and must still grant no authority."""
    directory = _directory(
        identity_row=IDENTITY_ROW, membership_row=_membership_row(role="unknown")
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert "role_grants_nothing:unknown" in result["blocked_reasons"]


def test_org_mismatch_is_denied_and_audited_as_cross_org() -> None:
    """If a foreign row reaches this code, the RLS boundary already failed."""
    directory = _directory(
        identity_row=IDENTITY_ROW,
        membership_row=_membership_row(organization_id="some-other-org"),
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is False
    assert "organization_mismatch" in result["blocked_reasons"]
    assert result["audit_event"]["event_type"] == "cross_org_access_attempt"


def test_every_denial_emits_an_audit_event() -> None:
    """A silent denial is an unobservable one."""
    for row in (
        _membership_row(state="revoked"),
        _membership_row(membership_source="client_header"),
        _membership_row(role_source="token_claim"),
        _membership_row(role="operator_internal"),
    ):
        directory = _directory(identity_row=IDENTITY_ROW, membership_row=row)
        result = resolve_persisted_membership(
            identity=VERIFIED_IDENTITY,
            organization_id=ORG,
            directory=directory,
        )
        assert result["allowed"] is False
        event = result["audit_event"]
        assert event is not None
        assert event["reasons"]
        # Not persisted: no provisioned database means no audit row.
        assert event["persisted"] is False


# ── claims that must stay false ─────────────────────────────────────────────


def test_customer_login_live_is_never_true_from_this_path() -> None:
    """Storage plus membership is still not login. Gate 69 owns that claim."""
    directory = _directory(
        identity_row=IDENTITY_ROW,
        membership_row=_membership_row(),
        **ALL_PRECONDITIONS,
    )
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=directory
    )
    assert result["allowed"] is True, result["blocked_reasons"]
    assert result["customer_login_live"] is False
    assert directory.status()["customer_login_live"] is False


def test_invariants_reject_a_denial_that_leaks_a_role() -> None:
    result = resolve_persisted_membership(
        identity=VERIFIED_IDENTITY, organization_id=ORG, directory=None
    )
    result["trusted_role"] = "org_owner"
    assert "denied_but_role_returned" in resolution_invariant_failures(result)


def test_controlled_customer_pilot_remains_no_go() -> None:
    """No code path in this gate may turn the pilot green.

    Asserted against the readiness doc rather than a constant, because the doc
    is what a human would read before inviting a customer.
    """
    doc = (
        ROOT / "docs" / "operations" / "398_GATE64_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Controlled customer pilot: NO_GO" in doc
    assert "Production rollout:        NO_GO" in doc
    assert "Customer login live:       NO" in doc
    assert "Production storage live:   NO" in doc
