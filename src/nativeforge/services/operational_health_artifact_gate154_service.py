"""Gate 154H: the health model, the registry and the runbook, written down.

Deterministic: reads no database, runs no shell and takes no arguments. Live
values - which unit is up, what a verifier returned this morning, how many
legacy gaps exist today - belong in the verifier that measures them.

Gate 153 learned this the expensive way: a committed artifact that pinned a row
count went stale within an hour because the readiness verifiers write fixture
rows between runs. Nothing here carries a live count.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.operational_health_model_service import (
    BACKEND_CODE_DIRTY,
    BACKEND_CODE_STALE,
    EXPECTED_FALSE_LANES,
    HEALTH_STATUSES,
    MIGRATION_AHEAD,
    MIGRATION_BEHIND,
    REQUIRED_COMPONENTS,
    STALE_STAMP_MISSING,
    STALE_STAMP_OLDER,
    build_operational_health_model,
)
from nativeforge.services.readiness_verifier_registry_service import (
    BACKUP_LANE_SEPARATION,
    build_verifier_registry,
)
from nativeforge.services.runbook_health_service import (
    HUMAN_APPROVAL_REQUIRED,
    HUMAN_BLOCKERS,
    OPERATOR_RUNNABLE,
    REMEDIES,
    build_runbook_health,
)

SCHEMA_VERSION = "nf_operational_health_gate154_artifacts_v1"

ARTIFACT_DIR = "artifacts/operational_health_gate154"

SURVEY_FILE = "observability_runbook_survey.json"
MODEL_FILE = "operational_health_model.json"
REGISTRY_FILE = "readiness_verifier_registry.json"
RUNBOOK_FILE = "runbook_health_summary.json"
NEXT_ACTION_FILE = "next_safe_action.json"
FAILURE_MODES_FILE = "known_failure_modes.json"
COCKPIT_FILE = "cockpit_operational_health_status.json"
READINESS_FILE = "operational_health_readiness.json"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    MODEL_FILE,
    REGISTRY_FILE,
    RUNBOOK_FILE,
    NEXT_ACTION_FILE,
    FAILURE_MODES_FILE,
    COCKPIT_FILE,
    READINESS_FILE,
)

FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

#: A model built from nothing. Every component unknown, which is the correct
#: answer when nobody supplied a fact, and it makes the artifact deterministic.
UNMEASURED_MODEL_NOTE = (
    "every component here is `unknown` because this artifact supplies no "
    "facts. That is the shape of the model, not a health reading. The live "
    "reading comes from "
    "scripts/verify_nativeforge_operational_health_runbook.sh."
)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "154",
        "subject": "observability and runbook health",
        "scope": "controlled_dev_demo",
        "what_is_observable_today": [
            "process liveness, from outside the app",
            "the repository HEAD, the build stamp sha, the backend runtime mode",
            "per-lane readiness, via each lane's own service",
            "27 verifiers, each answering one question when run by hand",
        ],
        "what_was_not_observable_before_this_gate": {
            "backend_stale_code": (
                "the surface built to answer it does not. `/backend/health` "
                "calls `detect_git_identity` at REQUEST time, so it reports the "
                "repository's HEAD, not the commit the process loaded. Proved "
                "by editing a tracked file and watching `source_dirty` flip "
                "with no restart. Nothing records a process-scoped commit."
            ),
            "stale_build_stamp": (
                "`--strict-public` checks the stamp TAG exists. It never "
                "compares the stamped sha to HEAD, so a build from an older "
                "commit passes every check while serving old JavaScript."
            ),
            "migration_drift": (
                "nothing compared the repository's highest revision to the "
                "database's current one. Gate 151 hit it at 0041 vs 0042 and "
                "found it by hand."
            ),
            "verifier_dependency_order": (
                "no registry existed. An operator learned the order by running "
                "things and reading failures."
            ),
            "next_safe_action": (
                "a module constant in the Gate 144 summary, reading "
                "`finish_the_controlled_beta_readiness_matrix`. That was true "
                "at Gate 144; the matrix was finished at Gate 145 and nine "
                "gates have happened since. A constant cannot go stale loudly."
            ),
        },
        "the_declaration_driven_services_this_gate_does_not_extend": {
            "gate32_observability_service": (
                "`resolve_observability` returns `production_monitoring: true` "
                "when a caller passes healthcheck_ready, support_owner_assigned, "
                "incident_escalation_ready and default_status='alert_ready'. "
                "Every input is a keyword argument. It measures nothing."
            ),
            "gate33_runbook_service": (
                "returns a hardcoded dict of six True values and a checklist "
                "whose evidence refs are `nf://` strings that point at nothing"
            ),
            "why_not_extended": (
                "Gate 65 drew this line first and said so in its own module: "
                "those services model what a demo surface should display and "
                "will promote a status on any non-empty string. Gate 154 "
                "cannot produce a production_monitoring claim by any path."
            ),
        },
        "what_remains_manual": [
            "restarting services",
            "running verifiers, in an order the registry now records",
            "noticing that a result is hours old; nothing records result age",
        ],
        "not_production_monitoring": True,
    }


def _model_shape() -> dict[str, Any]:
    model = build_operational_health_model()
    return {
        "schema_version": SCHEMA_VERSION,
        "note": UNMEASURED_MODEL_NOTE,
        "statuses": list(HEALTH_STATUSES),
        "required_components": list(REQUIRED_COMPONENTS),
        "expected_false_lanes": sorted(EXPECTED_FALSE_LANES),
        "unknown_is_not_a_pass": model["unknown_is_not_a_pass"],
        "a_lane_false_by_design_is_not_a_health_problem": model[
            "a_lane_false_by_design_is_not_a_health_problem"
        ],
        "unmeasured_model": {
            "operational_health_ready": model["operational_health_ready"],
            "overall_status": model["overall_status"],
            "by_status": model["by_status"],
            "required_unknown": model["required_unknown"],
            "blockers": model["blockers"],
        },
        "production_monitoring_active": False,
        "external_monitoring_configured": False,
        "alerting_configured": False,
        "shell_executed": False,
    }


def _runbook_shape() -> dict[str, Any]:
    runbook = build_runbook_health(health_model=build_operational_health_model())
    return {
        "schema_version": SCHEMA_VERSION,
        "note": UNMEASURED_MODEL_NOTE,
        "action_kinds": [OPERATOR_RUNNABLE, HUMAN_APPROVAL_REQUIRED, "NO_ACTION"],
        "remedied_blockers": sorted(REMEDIES),
        "human_blockers": sorted(HUMAN_BLOCKERS),
        "approval_gated_actions_carry_no_command": (
            "a runbook that prints the command next to the words 'needs "
            "approval' has already handed it over"
        ),
        "commands_are_checked_by": (
            "customer_auth_activation_runbook_service.command_is_secret_safe, "
            "Gate 121D's rule, imported rather than reimplemented"
        ),
        "unmeasured_runbook": {
            "action_count": runbook["action_count"],
            "operator_runnable_count": runbook["operator_runnable_count"],
            "human_approval_required_count": runbook["human_approval_required_count"],
        },
        "production_monitoring_active": False,
    }


def _next_action_shape() -> dict[str, Any]:
    runbook = build_runbook_health(health_model=build_operational_health_model())
    return {
        "schema_version": SCHEMA_VERSION,
        "note": UNMEASURED_MODEL_NOTE,
        "next_safe_action_when_nothing_is_supplied": runbook["next_safe_action"],
        "derived_not_declared": runbook["derived_not_declared"],
        "the_constant_it_replaces": {
            "module": "beta_onboarding_readiness_summary_service",
            "constant": "NEXT_SAFE_ACTION",
            "value": "finish_the_controlled_beta_readiness_matrix",
            "true_at": "Gate 144",
            "finished_at": "Gate 145",
            "gates_since": "146 through 154",
            "why_nothing_failed": "a constant cannot go stale loudly",
        },
        "live_reading_comes_from": (
            "scripts/verify_nativeforge_operational_health_runbook.sh"
        ),
    }


def _failure_modes() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "modes": [
            {
                "mode": "stale_frontend_stamp",
                "state": STALE_STAMP_OLDER,
                "detected_by": "Gate 154 health model, frontend_stamp component",
                "detected_by_strict_public": False,
                "why_not": (
                    "strict-public checks that the stamp tag EXISTS. It never "
                    "compares the sha, so an older stamp passes."
                ),
                "action": "./scripts/build_frontend_stamped.sh",
                "human_approval_required": False,
            },
            {
                "mode": "unstamped_build",
                "state": STALE_STAMP_MISSING,
                "detected_by": "strict-public, as identity_meta_present",
                "detected_by_strict_public": True,
                "why": "a plain `npm run build` overwrites dist/index.html",
                "action": "./scripts/build_frontend_stamped.sh",
                "human_approval_required": False,
            },
            {
                "mode": "backend_stale_code",
                "state": BACKEND_CODE_STALE,
                "detected_by": (
                    "Gate 154 health model, by comparing process start time to "
                    "HEAD commit time"
                ),
                "not_detectable_from": (
                    "/backend/health git_sha, which is measured at request time "
                    "from the repository and always agrees with HEAD"
                ),
                "action": "systemctl --user restart nativeforge-backend.service",
                "human_approval_required": False,
            },
            {
                "mode": "dirty_tree",
                "state": BACKEND_CODE_DIRTY,
                "detected_by": "Gate 154 health model",
                "action": "git status --porcelain --untracked-files=no",
                "human_approval_required": False,
            },
            {
                "mode": "migration_not_applied",
                "state": MIGRATION_BEHIND,
                "detected_by": "Gate 154 health model, migration_head component",
                "previously_detected_by": "nothing; Gate 151 found it by hand",
                "action": "alembic upgrade head",
                "human_approval_required": False,
            },
            {
                "mode": "migration_ahead_of_repository",
                "state": MIGRATION_AHEAD,
                "detected_by": "Gate 154 health model",
                "action": None,
                "human_approval_required": True,
                "why": (
                    "downgrading destroys data and which direction is correct "
                    "depends on why the branches differ"
                ),
            },
            {
                "mode": "prior_verifier_failed",
                "state": "verifier_result_unexpected",
                "detected_by": (
                    "Gate 154 health model, read against the registry's "
                    "expected_result for that verifier"
                ),
                "why_expected_result_matters": (
                    "a SKIP from the Gate 61/65 production backup harness is "
                    "correct; a SKIP from a readiness verifier would be a "
                    "finding. One universal PASS expectation would report the "
                    "production harness as broken forever."
                ),
                "action": "run that verifier alone and read its blocker line",
                "human_approval_required": False,
            },
            {
                "mode": "fixture_residue",
                "state": "fixture_residue_present",
                "detected_by": "verify_nativeforge_fixture_cleanliness.sh",
                "note": (
                    "readiness verifiers write fixture rows into the dev "
                    "database. Row counts and legacy gap counts MOVE between "
                    "runs: Gate 153 measured 6580 rows and 93 gaps, then 6842 "
                    "and 97 an hour later. That is residue, not drift in a lane."
                ),
                "human_approval_required": False,
            },
            {
                "mode": "legacy_evidence_gaps",
                "state": "legacy_evidence_gaps_present",
                "detected_by": "Gate 152 audit replay, Gate 153 restore",
                "must_not_be_backfilled": True,
                "why": (
                    "producing a digest for an intent that never had one is "
                    "fabricating evidence. A FALL in the count fails the lane."
                ),
                "human_approval_required": False,
            },
            {
                "mode": "customer_activation_blockers",
                "state": "awaiting_human_decision",
                "detected_by": "Gate 154 health model, as awaiting_human_decision",
                "not_a_blocker": True,
                "why": (
                    "these lanes are false by design. Counting them as health "
                    "blockers would keep the lane shut forever and send an "
                    "operator to fix something that is not broken."
                ),
                "human_approval_required": True,
            },
        ],
        "production_monitoring_active": False,
    }


def _cockpit_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "card": "operational_health",
        "scope": "controlled_dev_demo",
        "durability_lanes_shown": [
            "tenant_digest_persistence_live",
            "audit_replay_ready",
            "operational_backup_restore_ready",
            "operational_health_ready",
        ],
        "lane_evidence": "needs_a_verifier_run",
        "why_not_self_evidencing": (
            "a summary that supplied its own proof would be grading its own "
            "homework. Unsupplied means readiness_only, never operational."
        ),
        "blocked_lanes_shown": [
            "customer_auth_live",
            "verified_operational_binding",
            "consent_boundary_ready",
            "customer_beta_scope_approved",
            "source_monitoring_live",
            "email_delivery",
            "object_store_configured",
            "controlled_customer_pilot",
            "production_rollout",
        ],
        "production_monitoring_active": False,
        "production_monitoring_statement_on_card": True,
        "controlled_customer_pilot_active": False,
        "verifier_registry_summary_on_card": True,
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "operational_health_ready",
        "scope": "controlled_dev_demo",
        "what_it_means": (
            "the services, the migration state and the code freshness of this "
            "controlled_dev_demo deployment are modelled from measured facts, "
            "every named failure mode is detected and named, and the next safe "
            "action is derived rather than declared"
        ),
        "what_it_does_not_mean": [
            "that production is monitored; nothing is",
            "that alerting exists; nothing sends mail, SMS or a page",
            "that an external monitor is configured; nothing leaves this host",
            "that uptime, an SLO or an error budget is recorded; none is",
            "that incident response exists; there is a document, not a rota",
        ],
        "required_components": list(REQUIRED_COMPONENTS),
        "unknown_is_not_a_pass": True,
        "any_blocker_closes_the_lane": (
            "required-ness governs how much UNKNOWN is tolerated; it does not "
            "decide which faults count. A first draft weighed only required "
            "components and ignored an unexpected verifier result it had "
            "already named."
        ),
        "backup_lane_separation": dict(BACKUP_LANE_SEPARATION),
        "production_monitoring_active": False,
        "external_monitoring_configured": False,
        "alerting_configured": False,
    }


def build_operational_health_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; no database, no shell."""
    files = {
        SURVEY_FILE: _json(_survey()),
        MODEL_FILE: _json(_model_shape()),
        REGISTRY_FILE: _json(build_verifier_registry()),
        RUNBOOK_FILE: _json(_runbook_shape()),
        NEXT_ACTION_FILE: _json(_next_action_shape()),
        FAILURE_MODES_FILE: _json(_failure_modes()),
        COCKPIT_FILE: _json(_cockpit_status()),
        READINESS_FILE: _json(_readiness()),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_operational_health_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_operational_health_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def operational_health_artifact_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")

    return fails
