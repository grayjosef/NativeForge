"""Backup / restore readiness (Gate 65).

The Gate 61 storage approval required four things before production storage may
be called live: daily automated backups, PITR where the provider supports it, at
least one restore test recorded as an artifact, and documented RTO/RPO. None of
them can be *executed* without a provisioned managed instance, but all of them
can be gated now, so that when credentials arrive the answer is computed rather
than argued.

This module exists alongside the Block 73/77 demo services
(``gate32_backup_restore_service``, ``gate33_restore_rehearsal_service``) and
deliberately does not extend them. Those model what a demo surface should
display and will promote restore status on any non-empty
``restore_evidence_ref`` string — the string is never opened. That is fine for a
demo and useless as proof. Here, an artifact reference is a claim about a file,
and a claim about a file that does not exist is a blocked reason.

The distinctions this module refuses to blur, each of which is a way a backup
story is usually oversold:

  * A **policy** is a sentence. Automation is a configured job.
  * **PITR supported** is a provider capability. PITR enabled is a setting.
  * A **restore script existing** is not a restore having run.
  * A **restore having run** with no recorded artifact is untraceable.
  * An **artifact with no execution** is a file someone wrote by hand.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_backup_restore_readiness_v1"

STATES = frozenset(
    {
        "no_backup_path",
        "policy_declared_only",
        "automation_configured",
        "restore_unproven",
        "restore_proven",
        "unknown",
    }
)

# Recovery objectives must be real numbers. A missing RTO is not "best effort",
# it is an undefined recovery, and an absurd one is a typo that would be
# discovered during an incident.
MAX_SANE_RTO_MINUTES = 7 * 24 * 60
MAX_SANE_RPO_MINUTES = 7 * 24 * 60

# Anything matching these is never allowed into a serialized result, whatever
# field it arrives in. Cheaper than trusting every caller.
_SECRET_PATTERNS = (
    re.compile(r"[a-zA-Z0-9+]+://[^:/@\s]+:[^@\s]+@", re.I),  # url with password
    re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token)\s*[=:]\s*\S+"),
)

REDACTED = "[REDACTED]"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def redact(value: Any) -> Any:
    """Strip anything that looks like a credential out of a value.

    Applied to every string in the result, recursively. This is belt-and-braces
    over callers behaving well: a readiness report gets pasted into tickets and
    chat, so it is exactly the kind of artifact a password leaks through.
    """
    if isinstance(value, str):
        out = value
        for pattern in _SECRET_PATTERNS:
            if pattern.search(out):
                if pattern is _SECRET_PATTERNS[0]:
                    out = pattern.sub(
                        lambda m: (
                            m.group(0).split("://")[0]
                            + "://"
                            + m.group(0).split("://")[1].split(":")[0]
                            + f":{REDACTED}@"
                        ),
                        out,
                    )
                else:
                    out = pattern.sub(
                        lambda m: (
                            m.group(0).split("=")[0].split(":")[0] + f"={REDACTED}"
                        ),
                        out,
                    )
        return out
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def _positive_int(value: Any, ceiling: int) -> tuple[int | None, str | None]:
    """Return (minutes, problem). Rejects non-numbers, non-positives, absurdities."""
    if value is None:
        return None, "missing"
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None, "not_a_number"
    if minutes <= 0:
        return None, "not_positive"
    if minutes > ceiling:
        return None, "implausibly_large"
    return minutes, None


def build_backup_restore_readiness(
    *,
    provider: str | None = None,
    environment: str = "unprovisioned",
    database_url_present: bool | None = None,
    backup_policy_declared: bool = False,
    backup_automation_configured: bool = False,
    pitr_supported: bool = False,
    pitr_enabled: bool = False,
    restore_test_executed: bool = False,
    restore_artifact_path: str | None = None,
    rto_minutes: Any = None,
    rpo_minutes: Any = None,
    rls_proof_passed_after_restore: bool = False,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Compute backup/restore readiness. Never claims execution it cannot see.

    ``database_url_present`` defaults to reading the environment rather than
    accepting a caller's word, but stays overridable so tests need no monkey
    patching. The value itself is never read into the result.
    """
    blocked: list[str] = []
    warnings: list[str] = []
    proof_artifacts: list[str] = []

    if database_url_present is None:
        database_url_present = bool(os.environ.get("DATABASE_URL"))

    # ── policy and automation ────────────────────────────────────────────
    if not backup_policy_declared:
        blocked.append("backup_policy_not_declared")
    if not backup_automation_configured:
        blocked.append("backup_automation_not_configured")
    elif not database_url_present:
        # Automation configured against nothing is a claim about a database that
        # does not exist here.
        blocked.append("backup_automation_configured_without_database")

    if not database_url_present:
        blocked.append("no_database_configured")

    # ── PITR ─────────────────────────────────────────────────────────────
    # Supported is a provider capability; enabled is a setting someone turned
    # on. Conflating them is the most common way a backup story is oversold.
    if pitr_enabled and not pitr_supported:
        blocked.append("pitr_enabled_but_not_supported_by_provider")
    if pitr_supported and not pitr_enabled:
        warnings.append("pitr_supported_but_not_enabled")
    if not pitr_supported:
        warnings.append("pitr_not_supported_by_provider")

    # ── restore proof ────────────────────────────────────────────────────
    # Execution and artifact are checked as a pair in both directions.
    artifact_ok = False
    if restore_artifact_path:
        root = artifact_root or Path.cwd()
        candidate = Path(restore_artifact_path)
        resolved = candidate if candidate.is_absolute() else (root / candidate)
        if resolved.is_file():
            artifact_ok = True
            proof_artifacts.append(str(restore_artifact_path))
        else:
            # The Block 73 services accept any non-empty string here. This one
            # opens it.
            blocked.append("restore_artifact_path_does_not_exist")

    if not restore_test_executed and not artifact_ok:
        blocked.append("restore_never_executed")
    elif restore_test_executed and not artifact_ok:
        blocked.append("restore_executed_without_recorded_artifact")
    elif artifact_ok and not restore_test_executed:
        # A file on disk is not evidence that anything ran.
        blocked.append("restore_artifact_without_execution")

    if restore_test_executed and artifact_ok and not rls_proof_passed_after_restore:
        # A restored database that lost its RLS policies is a tenant-isolation
        # incident wearing a recovery costume.
        blocked.append("rls_not_reproven_after_restore")

    # ── recovery objectives ──────────────────────────────────────────────
    rto, rto_problem = _positive_int(rto_minutes, MAX_SANE_RTO_MINUTES)
    if rto_problem:
        blocked.append(f"rto_invalid:{rto_problem}")
    rpo, rpo_problem = _positive_int(rpo_minutes, MAX_SANE_RPO_MINUTES)
    if rpo_problem:
        blocked.append(f"rpo_invalid:{rpo_problem}")

    if rto is not None and rpo is not None and rpo > rto:
        # Not fatal, but almost always a mix-up worth surfacing.
        warnings.append("rpo_exceeds_rto_check_these_are_not_swapped")

    # ── state ────────────────────────────────────────────────────────────
    reached = "no_backup_path"
    if backup_policy_declared:
        reached = "policy_declared_only"
    if backup_policy_declared and backup_automation_configured and database_url_present:
        reached = "automation_configured"
        if restore_test_executed or artifact_ok:
            reached = "restore_unproven"
        if (
            restore_test_executed
            and artifact_ok
            and rls_proof_passed_after_restore
            and rto is not None
            and rpo is not None
        ):
            reached = "restore_proven"

    ready = not blocked and reached == "restore_proven"

    result = {
        "schema_version": SCHEMA_VERSION,
        "state": reached,
        "ready": ready,
        "blocked_reasons": blocked,
        "warnings": warnings,
        "proof_artifacts": proof_artifacts,
        "provider": provider,
        "environment": environment,
        "database_url_present": bool(database_url_present),
        # The URL itself is never carried, only whether one existed.
        "secrets_redacted": True,
        "backup_policy_declared": bool(backup_policy_declared),
        "backup_automation_configured": bool(backup_automation_configured),
        "pitr_supported": bool(pitr_supported),
        "pitr_enabled": bool(pitr_enabled),
        "restore_test_executed": bool(restore_test_executed),
        "restore_artifact_recorded": artifact_ok,
        "rls_proof_passed_after_restore": bool(rls_proof_passed_after_restore),
        "rto_minutes": rto,
        "rpo_minutes": rpo,
        # Backup readiness is one precondition of production storage, never the
        # whole thing. Storage also needs the approval token, migrations at
        # head, and the RLS proof — see postgres_membership_directory_service.
        "production_storage_live_claimed": False,
        "customer_persistence_claimed": False,
    }
    return _json_safe(redact(result))


def backup_restore_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("state") not in STATES:
        fails.append("state_invalid")

    if result.get("ready"):
        if result.get("blocked_reasons"):
            fails.append("ready_with_blocked_reasons")
        if result.get("state") != "restore_proven":
            fails.append("ready_without_restore_proven_state")
        for required in (
            "backup_policy_declared",
            "backup_automation_configured",
            "restore_test_executed",
            "restore_artifact_recorded",
            "rls_proof_passed_after_restore",
            "database_url_present",
        ):
            if not result.get(required):
                fails.append(f"ready_without:{required}")
        if result.get("rto_minutes") is None:
            fails.append("ready_without:rto_minutes")
        if result.get("rpo_minutes") is None:
            fails.append("ready_without:rpo_minutes")

    if result.get("state") == "restore_proven" and not result.get(
        "restore_artifact_recorded"
    ):
        fails.append("restore_proven_without_artifact")
    if result.get("restore_artifact_recorded") and not result.get("proof_artifacts"):
        fails.append("artifact_recorded_without_path")
    if result.get("pitr_enabled") and not result.get("pitr_supported"):
        fails.append("pitr_enabled_without_support")

    # These two may never be true from this module, whatever the inputs say.
    for forbidden in (
        "production_storage_live_claimed",
        "customer_persistence_claimed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    # A credential must never survive into a serialized readiness report.
    #
    # Scan with the redaction markers removed first. A redacted URL still reads
    # as "scheme://user:something@host" to the pattern, so scanning the raw blob
    # would flag the redaction's own output and make this invariant useless.
    # Stripping the markers leaves "user:@host", which the pattern correctly
    # does not match because it requires a non-empty password segment.
    blob = json.dumps(result)
    for marker in (REDACTED, "***"):
        blob = blob.replace(marker, "")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(blob):
            fails.append("unredacted_secret_in_result")
            break
    return fails
