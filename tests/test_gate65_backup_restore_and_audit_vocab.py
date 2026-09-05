"""Tests: Gate 65 backup/restore readiness and security audit vocabulary.

Two subjects. The backup half is almost entirely about refusing to call a
recovery story proven — a policy is not automation, supported is not enabled, a
script is not an execution, and an execution with no artifact is untraceable.
The audit half proves the vocabulary landed without breaking the 37 verbs that
were already there, and that the one verb the schema cannot represent is
actually refused at the write path rather than merely documented.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from nativeforge.domain.enums import (
    SECURITY_AUDIT_ACTIONS,
    UNPERSISTABLE_AUDIT_ACTIONS,
    AuditAction,
    audit_action_is_persistable,
)
from nativeforge.services.backup_restore_readiness_service import (
    backup_restore_readiness_invariant_failures,
    build_backup_restore_readiness,
    redact,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_nativeforge_backup_restore.sh"

# Everything needed for a proven restore, so individual pieces can be removed.
FULL = {
    "provider": "example-managed-postgres",
    "environment": "dr-drill",
    "database_url_present": True,
    "backup_policy_declared": True,
    "backup_automation_configured": True,
    "pitr_supported": True,
    "pitr_enabled": True,
    "restore_test_executed": True,
    "rls_proof_passed_after_restore": True,
    "rto_minutes": 240,
    "rpo_minutes": 60,
}


@pytest.fixture
def artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    """A real file on disk, because the service opens the path it is given."""
    p = tmp_path / "nf_restore_proof_20260901T031500Z.json"
    p.write_text(json.dumps({"artifact_id": "nf_restore_test"}), encoding="utf-8")
    return p


# ── the ladder of things that are not readiness ─────────────────────────────


def test_nothing_configured_is_not_ready() -> None:
    r = build_backup_restore_readiness()
    assert r["ready"] is False
    assert r["state"] == "no_backup_path"
    assert "backup_policy_not_declared" in r["blocked_reasons"]
    assert not backup_restore_readiness_invariant_failures(r)


def test_backup_policy_alone_is_not_ready() -> None:
    """A policy is a sentence. It is not a configured job."""
    r = build_backup_restore_readiness(backup_policy_declared=True)
    assert r["ready"] is False
    assert r["state"] == "policy_declared_only"
    assert "backup_automation_not_configured" in r["blocked_reasons"]


def test_database_url_alone_is_not_ready() -> None:
    r = build_backup_restore_readiness(database_url_present=True)
    assert r["ready"] is False
    assert "backup_policy_not_declared" in r["blocked_reasons"]
    assert "backup_automation_not_configured" in r["blocked_reasons"]


def test_automation_claimed_without_a_database_is_blocked() -> None:
    """Automation against nothing is a claim about a database that isn't there."""
    r = build_backup_restore_readiness(
        backup_policy_declared=True,
        backup_automation_configured=True,
        database_url_present=False,
    )
    assert r["ready"] is False
    assert "backup_automation_configured_without_database" in r["blocked_reasons"]


def test_pitr_supported_alone_is_not_ready_and_warns() -> None:
    """Supported is a provider capability. Enabled is a setting someone turned on."""
    r = build_backup_restore_readiness(pitr_supported=True)
    assert r["ready"] is False
    assert "pitr_supported_but_not_enabled" in r["warnings"]
    assert r["pitr_enabled"] is False


def test_pitr_enabled_without_provider_support_is_blocked() -> None:
    """Claiming PITR a provider does not offer is a false recovery capability."""
    r = build_backup_restore_readiness(
        **{**FULL, "pitr_supported": False, "pitr_enabled": True}
    )
    assert r["ready"] is False
    assert "pitr_enabled_but_not_supported_by_provider" in r["blocked_reasons"]
    assert "pitr_enabled_without_support" in (
        backup_restore_readiness_invariant_failures(r)
    )


def test_pitr_enabled_without_restore_artifact_is_not_ready() -> None:
    r = build_backup_restore_readiness(**FULL)  # no artifact path supplied
    assert r["ready"] is False
    assert "restore_executed_without_recorded_artifact" in r["blocked_reasons"]


def test_restore_artifact_without_execution_is_not_ready(
    artifact: pathlib.Path,
) -> None:
    """A file on disk is not evidence that anything ran."""
    r = build_backup_restore_readiness(
        **{**FULL, "restore_test_executed": False},
        restore_artifact_path=str(artifact),
    )
    assert r["ready"] is False
    assert "restore_artifact_without_execution" in r["blocked_reasons"]


def test_restore_execution_without_artifact_is_not_ready() -> None:
    r = build_backup_restore_readiness(**{**FULL, "restore_test_executed": True})
    assert r["ready"] is False
    assert "restore_executed_without_recorded_artifact" in r["blocked_reasons"]


def test_nonexistent_artifact_path_is_blocked_not_believed() -> None:
    """The Block 73 service accepts any non-empty string here. This one opens it."""
    r = build_backup_restore_readiness(
        **FULL, restore_artifact_path="artifacts/nope/does_not_exist.json"
    )
    assert r["ready"] is False
    assert "restore_artifact_path_does_not_exist" in r["blocked_reasons"]
    assert r["restore_artifact_recorded"] is False


def test_restore_without_reproven_rls_is_blocked(artifact: pathlib.Path) -> None:
    """A restored DB that lost its RLS policies is an isolation incident."""
    r = build_backup_restore_readiness(
        **{**FULL, "rls_proof_passed_after_restore": False},
        restore_artifact_path=str(artifact),
    )
    assert r["ready"] is False
    assert "rls_not_reproven_after_restore" in r["blocked_reasons"]


@pytest.mark.parametrize("field", ["rto_minutes", "rpo_minutes"])
def test_missing_recovery_objective_blocks(field: str, artifact: pathlib.Path) -> None:
    r = build_backup_restore_readiness(
        **{**FULL, field: None}, restore_artifact_path=str(artifact)
    )
    assert r["ready"] is False
    assert f"{field.split('_')[0]}_invalid:missing" in r["blocked_reasons"]


@pytest.mark.parametrize(
    "value,problem",
    [
        (0, "not_positive"),
        (-5, "not_positive"),
        ("soon", "not_a_number"),
        (999999, "implausibly_large"),
    ],
)
def test_nonsense_recovery_objectives_are_rejected(
    value: object, problem: str, artifact: pathlib.Path
) -> None:
    r = build_backup_restore_readiness(
        **{**FULL, "rto_minutes": value}, restore_artifact_path=str(artifact)
    )
    assert r["ready"] is False
    assert f"rto_invalid:{problem}" in r["blocked_reasons"]


def test_swapped_objectives_warn(artifact: pathlib.Path) -> None:
    """RPO above RTO is nearly always a transcription error."""
    r = build_backup_restore_readiness(
        **{**FULL, "rto_minutes": 60, "rpo_minutes": 240},
        restore_artifact_path=str(artifact),
    )
    assert "rpo_exceeds_rto_check_these_are_not_swapped" in r["warnings"]


# ── the path that can succeed ───────────────────────────────────────────────


def test_full_chain_reaches_readiness_in_the_modeled_path(
    artifact: pathlib.Path,
) -> None:
    """The gate must be passable, or it is theatre rather than a gate."""
    r = build_backup_restore_readiness(**FULL, restore_artifact_path=str(artifact))
    assert r["blocked_reasons"] == []
    assert r["state"] == "restore_proven"
    assert r["ready"] is True
    assert r["restore_artifact_recorded"] is True
    assert r["proof_artifacts"] == [str(artifact)]
    assert not backup_restore_readiness_invariant_failures(r)


def test_readiness_never_claims_storage_live_or_persistence(
    artifact: pathlib.Path,
) -> None:
    """Backup readiness is one precondition of storage, never the whole thing."""
    r = build_backup_restore_readiness(**FULL, restore_artifact_path=str(artifact))
    assert r["ready"] is True
    assert r["production_storage_live_claimed"] is False
    assert r["customer_persistence_claimed"] is False


def test_invariants_reject_a_forged_ready_result() -> None:
    r = build_backup_restore_readiness()
    r["ready"] = True
    fails = backup_restore_readiness_invariant_failures(r)
    assert "ready_with_blocked_reasons" in fails
    assert "ready_without_restore_proven_state" in fails


def test_invariants_reject_a_forged_storage_live_claim(
    artifact: pathlib.Path,
) -> None:
    r = build_backup_restore_readiness(**FULL, restore_artifact_path=str(artifact))
    r["production_storage_live_claimed"] = True
    assert "forbidden_claim:production_storage_live_claimed" in (
        backup_restore_readiness_invariant_failures(r)
    )


# ── secret handling ─────────────────────────────────────────────────────────


def test_result_never_carries_the_database_url() -> None:
    r = build_backup_restore_readiness(database_url_present=True)
    blob = json.dumps(r)
    assert "postgresql://" not in blob
    assert r["database_url_present"] is True
    assert r["secrets_redacted"] is True


def test_password_bearing_strings_are_redacted_out_of_the_result() -> None:
    """A readiness report gets pasted into tickets, so it must not carry secrets."""
    r = build_backup_restore_readiness(
        provider="postgresql://nf_app:hunter2@db.internal:5432/nf",
        database_url_present=True,
    )
    blob = json.dumps(r)
    assert "hunter2" not in blob
    assert not backup_restore_readiness_invariant_failures(r)


def test_invariants_catch_an_unredacted_secret() -> None:
    r = build_backup_restore_readiness(database_url_present=True)
    r["provider"] = "postgresql://nf_app:hunter2@db.internal:5432/nf"
    assert "unredacted_secret_in_result" in (
        backup_restore_readiness_invariant_failures(r)
    )


@pytest.mark.parametrize(
    "raw",
    [
        "postgresql://u:p@h:5432/d",
        "password=supersecret",
        "api_key: abc123def",
        "token=eyJhbGciOi",
    ],
)
def test_redact_strips_credential_shapes(raw: str) -> None:
    out = redact(raw)
    for leak in ("supersecret", "abc123def", "eyJhbGciOi"):
        assert leak not in out
    assert "p@h" not in out or ":p@" not in out


def test_redact_recurses_into_containers() -> None:
    out = redact({"a": ["password=leaky"], "b": {"c": "password=alsoleaky"}})
    blob = json.dumps(out)
    assert "leaky" not in blob
    assert "alsoleaky" not in blob


# ── the verify script ───────────────────────────────────────────────────────


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=env,  # deliberately no DATABASE_URL
    )


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111, "script must be executable"


def test_dry_run_needs_no_credentials_and_does_not_fail() -> None:
    r = _run("--dry-run")
    assert "RESULT=FAIL" not in r.stdout, r.stdout
    assert r.returncode == 0
    assert "check=dry_run_mode status=PASS" in r.stdout


def test_dry_run_reports_the_four_approval_requirements_honestly() -> None:
    """Each must be reported as not-done, not quietly omitted."""
    r = _run("--dry-run")
    for name in (
        "backup_policy_declared",
        "backup_automation_configured",
        "pitr_enabled",
        "restore_test_executed",
        "restore_artifact_recorded",
    ):
        assert f"check={name} status=SKIP" in r.stdout, f"{name} not reported as SKIP"


def test_dry_run_proves_its_own_redaction_and_guards() -> None:
    r = _run("--dry-run")
    assert "check=database_url_redacted status=PASS" in r.stdout
    assert "hunter2" not in r.stdout
    assert "check=password_detection_self_test status=PASS" in r.stdout
    # The overwrite guard depends on parsing a database name out of a URL.
    assert "check=same_database_guard_self_test status=PASS" in r.stdout


def test_rto_and_rpo_are_documented() -> None:
    r = _run("--dry-run")
    assert "check=rto_defined status=PASS" in r.stdout
    assert "check=rpo_defined status=PASS" in r.stdout


@pytest.mark.parametrize(
    "mode", ["--check-config", "--verify-backup", "--verify-restore"]
)
def test_database_modes_skip_without_credentials(mode: str) -> None:
    r = _run(mode)
    assert r.returncode == 0
    assert "RESULT=SKIP" in r.stdout
    assert "check=database_url_present status=SKIP" in r.stdout


def test_strict_fails_without_credentials() -> None:
    r = _run("--strict")
    assert r.returncode == 1
    assert "RESULT=FAIL" in r.stdout
    assert "check=database_url_present status=FAIL" in r.stdout


def test_no_mode_defaults_to_dry_run() -> None:
    r = _run()
    assert "verify_mode=dry-run" in r.stdout
    assert r.returncode == 0


def test_unknown_argument_is_rejected() -> None:
    r = _run("--restore-everything-now")
    assert r.returncode == 2
    assert "RESULT=FAIL" in r.stdout


def test_script_declares_every_required_check_name() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    for name in (
        "database_url_present",
        "database_url_redacted",
        "pg_dump_available",
        "pg_restore_available",
        "backup_policy_declared",
        "backup_automation_configured",
        "pitr_enabled",
        "restore_test_executed",
        "restore_artifact_recorded",
        "rto_defined",
        "rpo_defined",
        "result",
    ):
        assert f"say {name} " in body, f"missing check: {name}"


def test_script_refuses_to_restore_over_the_source() -> None:
    """A restore proof that overwrites the database it proves is an outage."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "restore_target_is_not_source" in body
    assert "refusing to overwrite the source" in body
    # The guard must compare both the whole URL and the database name.
    assert '"$TARGET" == "$DATABASE_URL"' in body
    assert '"$SRC_DB" == "$TGT_DB"' in body


def test_script_never_echoes_the_raw_url() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ('echo "$DATABASE_URL"', "echo $DATABASE_URL"):
        assert forbidden not in body


def test_artifacts_go_under_the_declared_untracked_directory() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    assert "artifacts/gate65_backup_restore" in body


# ── audit vocabulary ────────────────────────────────────────────────────────

EXPECTED_SECURITY_VERBS = {
    "tenant_access_denied",
    "cross_org_access_attempt",
    "membership_created",
    "membership_revoked",
    "membership_expired",
    "role_changed",
    "authority_proof_submitted",
    "authority_proof_verified",
    "authority_sensitive_action_blocked",
    "source_candidate_promoted",
    "source_candidate_blocked",
    "feedback_alert_attempted",
    "feedback_alert_failed",
}

# The 37 that existed before Gate 65. Listed explicitly so a future deletion is
# caught rather than absorbed.
PREEXISTING_VERBS = {
    "artifact_created",
    "review_requested",
    "approved",
    "rejected",
    "finalized",
    "reset_to_draft",
    "transition_rejected",
    "profile_created",
    "profile_updated",
    "profile_exported",
    "nofo_extraction_completed",
    "spark_scored",
    "spark_score_overridden",
    "grant_pursuit_created",
    "grant_pursuit_updated",
    "pursuit_task_created",
    "pursuit_task_updated",
    "pursuit_calendar_event_created",
    "pursuit_calendar_event_updated",
    "form_package_created",
    "sf424_preview_regenerated",
    "org_data_snapshot_exported",
    "pursuit_brief_generated",
    "discovery_intake_run_completed",
    "discovery_review_item_created",
    "discovery_review_item_updated",
    "discovery_quality_scored",
    "source_check_run_created",
    "source_check_run_completed",
    "source_freshness_evaluated",
    "source_marked_overdue",
    "operator_action_created",
    "operator_action_updated",
    "operator_action_resolved",
    "operator_action_deferred",
    "operator_action_dismissed",
    "operator_action_reopened",
}


# Verbs added after Gate 65, each by a gate that had to justify it. Listed
# here rather than folded into PREEXISTING_VERBS so the two sets keep meaning
# what their names say, and so the closed-set assertion below stays closed.
#
# Gate 142 added both of these for digest delivery. Neither is a security verb:
# a tenant digest in the security event stream teaches every reader filtering
# for security events to ignore it.
POST_GATE_65_VERBS = {
    "digest_delivery_intent_recorded",
    "digest_delivery_refused",
}


@pytest.mark.parametrize("verb", sorted(EXPECTED_SECURITY_VERBS))
def test_all_thirteen_security_verbs_exist(verb: str) -> None:
    assert AuditAction(verb).value == verb


def test_security_verb_set_is_exactly_the_thirteen() -> None:
    assert {a.value for a in SECURITY_AUDIT_ACTIONS} == EXPECTED_SECURITY_VERBS


@pytest.mark.parametrize("verb", sorted(PREEXISTING_VERBS))
def test_preexisting_verbs_are_not_removed(verb: str) -> None:
    assert AuditAction(verb).value == verb


def test_member_count_is_the_sum_and_nothing_extra() -> None:
    assert len(PREEXISTING_VERBS) == 37
    assert len(EXPECTED_SECURITY_VERBS) == 13
    assert len(POST_GATE_65_VERBS) == 2
    assert {a.value for a in AuditAction} == (
        PREEXISTING_VERBS | EXPECTED_SECURITY_VERBS | POST_GATE_65_VERBS
    )


@pytest.mark.parametrize("verb", sorted(POST_GATE_65_VERBS))
def test_a_later_verb_exists_and_is_not_a_security_verb(verb: str) -> None:
    assert AuditAction(verb).value == verb
    assert verb not in EXPECTED_SECURITY_VERBS


def test_no_audit_verb_asserts_that_something_was_sent() -> None:
    """`digest_delivery_sent` does not exist; nothing can produce it."""
    assert not [a.value for a in AuditAction if a.value.endswith("_sent")]


def test_every_verb_fits_the_action_column() -> None:
    """nf_audit_events.action is String(64)."""
    for action in AuditAction:
        assert len(action.value) <= 64, action.value


# ── the verb that must not be persisted ─────────────────────────────────────


def test_cross_org_access_attempt_is_marked_unpersistable() -> None:
    assert AuditAction.cross_org_access_attempt in UNPERSISTABLE_AUDIT_ACTIONS
    assert audit_action_is_persistable(AuditAction.cross_org_access_attempt) is False


def test_other_security_verbs_are_persistable_once_a_database_exists() -> None:
    for action in SECURITY_AUDIT_ACTIONS - UNPERSISTABLE_AUDIT_ACTIONS:
        assert audit_action_is_persistable(action) is True, action.value


def test_unknown_verbs_are_not_persistable() -> None:
    """Deny by default: an unrecognised verb does not belong in an audit trail."""
    assert audit_action_is_persistable("not_a_real_verb") is False
    assert audit_action_is_persistable("") is False


def test_repository_refuses_to_persist_cross_org_access_attempt() -> None:
    """The rule has teeth at the write path, not only in a docstring.

    It must raise rather than silently drop: a security event that vanishes is
    worse than a request that fails, because nobody finds out.
    """
    from nativeforge.repositories.audit_events import append_org_audit_event

    with pytest.raises(ValueError, match="cannot be persisted"):
        append_org_audit_event(
            None,  # never reached; the guard runs before any session use
            organization_id=None,
            is_demo=False,
            action=AuditAction.cross_org_access_attempt,
            payload={},
            actor_id=None,
        )


def test_the_guard_names_the_plan_doc() -> None:
    """Whoever hits this error needs to know what unblocks it."""
    from nativeforge.repositories import audit_events

    src = pathlib.Path(audit_events.__file__).read_text(encoding="utf-8")
    assert "401_GATE65_AUDIT_ACTION_VOCABULARY_AND_0028_PLAN" in src


def test_audit_persistence_is_not_claimed_live() -> None:
    doc = (
        ROOT
        / "docs"
        / "operations"
        / "401_GATE65_AUDIT_ACTION_VOCABULARY_AND_0028_PLAN.md"
    ).read_text(encoding="utf-8")
    assert "Audit persistence:         NOT WIRED" in doc
    assert "Production storage live:   NO" in doc
