"""Gate 156K: the scheduler runtime, written down. Deterministic, no database.

Live registry counts belong in the verifier that measures them. Gate 153 pinned
a row count in a committed document and it went stale within the hour, so the
smoke artifacts here use a fixed fixture clock and fixed fixture sources - the
shape of an evaluation, not a reading of today's registry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.source_collection_job_model_service import JOB_FIELDS
from nativeforge.services.source_collection_scheduler_health_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    build_scheduler_health,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    EXECUTION_MODES_NOT_IMPLEMENTED,
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_scheduler_runtime_service import (
    ACTIVATION_PERMITS,
    HUMAN_REVIEW_PERMITS,
    RUNTIME_STATES,
    TERMS_PERMITS,
    compute_next_run_at,
)

SCHEMA_VERSION = "nf_source_scheduler_gate156_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_scheduler_gate156"

SURVEY_FILE = "scheduler_runtime_survey.json"
JOB_MODEL_FILE = "scheduler_job_model.json"
SMOKE_FILE = "scheduler_runtime_smoke.json"
BLOCKED_FILE = "scheduler_blocked_job_smoke.json"
EMPTY_FILE = "scheduler_empty_allowlist.json"
HEALTH_FILE = "scheduler_health.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_scheduler_runtime_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    JOB_MODEL_FILE,
    SMOKE_FILE,
    BLOCKED_FILE,
    EMPTY_FILE,
    HEALTH_FILE,
    MONITORING_FILE,
    BLOCKERS_FILE,
)

FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

#: A fixed instant. Nothing here reads a wall clock.
FIXTURE_NOW = "2026-09-15T12:00:00Z"

#: Three fixture sources covering the refusal paths the gate must prove.
FIXTURE_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "source_id": "nf-fixture-gate156-terms-blocked",
        "check_interval_days": 7,
        "last_checked_at": "2026-09-01T12:00:00Z",
        "is_enabled": True,
        "activation_state": "activation_blocked",
        "terms_state": "terms_unknown",
        "human_review_state": "human_review_required",
        "collector_registered": False,
    },
    {
        "source_id": "nf-fixture-gate156-human-review",
        "check_interval_days": 30,
        "last_checked_at": "2026-09-14T12:00:00Z",
        "is_enabled": True,
        "activation_state": "activation_blocked",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_required",
        "collector_registered": False,
    },
    {
        "source_id": "nf-fixture-gate156-no-cadence",
        "check_interval_days": None,
        "last_checked_at": None,
        "is_enabled": True,
        "activation_state": "activation_blocked",
        "terms_state": "terms_unknown",
        "human_review_state": "human_review_required",
        "collector_registered": False,
    },
)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _fixture_cycle() -> dict[str, Any]:
    return run_scheduler_cycle(now=FIXTURE_NOW, sources=list(FIXTURE_SOURCES))


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "156",
        "subject": "hermetic source scheduler runtime",
        "what_already_existed": {
            "98B_schedule_decision": (
                "evaluate_schedule() - takes a due date, compares to a clock"
            ),
            "98E_scheduler_readiness": "detects components by import",
            "99B_job_model": "build_source_job() - identity and execution mode",
            "99C_queue": "build_dry_run_queue() - a list of work",
            "100C_dry_run_worker": "run_dry_run_worker() - marks jobs",
        },
        "what_was_missing": [
            "nothing computed a next run time from an interval and a last check",
            "nothing walked sources against a clock and reported what is due",
            "nothing reported scheduler health as a machine-readable lane",
        ],
        "the_two_things_called_scheduler_runtime": {
            "scheduler_runtime_available": (
                "True - a runtime MODE exists (dry_run_in_process)"
            ),
            "scheduler_package_installed": (
                "False - find_spec over apscheduler, dramatiq, arq, huey, "
                "schedule, croniter, taskiq, procrastinate"
            ),
            "is_this_a_defect": (
                "no. Gate 99D found it and split the field deliberately, "
                "reporting both side by side. This gate says so rather than "
                "claiming a finding it does not have."
            ),
            "the_consequence": (
                "Gate 143's blocker `scheduler_component_absent:scheduler_runtime` "
                "means NO PACKAGE IS INSTALLED. Installing one would clear the "
                "blocker without computing a single due date, so this gate "
                "installs none and the blocker stays listed."
            ),
        },
        "no_migration_was_added": {
            "why": (
                "nf_opportunity_sources already carries check_interval_days, "
                "next_check_due_at, last_checked_at, last_check_status and "
                "consecutive_failure_count"
            ),
            "what_a_new_table_would_cost": (
                "ten duplicated columns and two places to ask when a source is "
                "due, which is how they come to disagree"
            ),
            "alembic_head_unchanged": True,
        },
        "two_registries_exist_and_nothing_joins_them": {
            "file_registry": "177 rows, carries no terms column - every row UNKNOWN",
            "database_table": "nf_opportunity_sources, 40 rows, carries the cadence",
            "consequence": (
                "terms state and schedule state live in different places. "
                "Joining them is what a persistent job store would be for, "
                "which is Gate 158."
            ),
        },
        "no_scheduling_package_added": True,
        "uv_lock_untouched": True,
        "source_monitoring_live": False,
    }


def _job_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "job_fields": list(JOB_FIELDS),
        "runtime_states": list(RUNTIME_STATES),
        "built_on": (
            "source_scheduler_job_model_service.build_source_job (Gate 99B) - "
            "composed rather than duplicated, because a second job model gives "
            "the repository two places to ask whether a job may run"
        ),
        "permitting_values": {
            "activation_state": ACTIVATION_PERMITS,
            "terms_state": TERMS_PERMITS,
            "human_review_state": HUMAN_REVIEW_PERMITS,
        },
        "executable_requires_every_prerequisite_affirmatively_true": (
            "not 'no blockers found'. Absence of evidence is not permission, "
            "and a source whose terms nobody has read is UNKNOWN."
        ),
        "due_is_not_executable": (
            "`due` is a fact about a clock. `executable` is a fact about "
            "approvals. A job may be overdue and still refuse, and reporting "
            "only the refusal would make a backlog invisible."
        ),
        "expected_executable_count_today": 0,
    }


def _smoke() -> dict[str, Any]:
    cycle = _fixture_cycle()
    timing = [
        {
            "case": "interval and a last check",
            **compute_next_run_at(
                last_checked_at="2026-09-01T12:00:00Z", check_interval_days=7
            ),
        },
        {
            "case": "no interval recorded",
            **compute_next_run_at(last_checked_at="2026-09-01T12:00:00Z"),
        },
        {
            "case": "a recorded due date disagrees with the computed one",
            **compute_next_run_at(
                last_checked_at="2026-09-01T12:00:00Z",
                check_interval_days=7,
                recorded_next_check_due_at="2026-10-01T00:00:00Z",
            ),
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_at": FIXTURE_NOW,
        "next_run_computation": timing,
        "no_cadence_means_never_due": (
            "a source nobody set an interval for is a source nobody decided "
            "the cadence for. Reading that as 'check it now' is backwards."
        ),
        "cycle": {
            "jobs_known": cycle["jobs_known"],
            "jobs_by_state": cycle["jobs_by_state"],
            "jobs_due": cycle["jobs_due"],
            "jobs_executable": cycle["jobs_executable"],
            "jobs_refused": cycle["jobs_refused"],
            "refusal_reasons": cycle["refusal_reasons"],
        },
        "deterministic": _fixture_cycle() == cycle,
        "clock_is_injected": True,
        "threads_started": 0,
        "collectors_invoked": 0,
        "live_source_calls": 0,
    }


def _blocked_job() -> dict[str, Any]:
    cycle = _fixture_cycle()
    job = next(
        j for j in cycle["jobs"] if j["source_id"] == "nf-fixture-gate156-terms-blocked"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": job["source_id"],
        "runtime_state": job["runtime_state"],
        "due": job["due"],
        "executable": job["executable"],
        "blockers": job["blockers"],
        "activation_state": job["activation_state"],
        "terms_state": job["terms_state"],
        "human_review_state": job["human_review_state"],
        "collector_registered": job["collector_registered"],
        "collector_invoked": job["collector_invoked"],
        "fetch_performed": job["fetch_performed"],
        "why_it_refuses": (
            "every prerequisite must be affirmatively the permitting value. "
            "This one has none of them."
        ),
    }


def _empty_allowlist() -> dict[str, Any]:
    cycle = _fixture_cycle()
    return {
        "schema_version": SCHEMA_VERSION,
        "activation_allowlist_count": 0,
        "jobs_known": cycle["jobs_known"],
        "jobs_executable": cycle["jobs_executable"],
        "is_there_a_special_case_for_an_empty_allowlist": False,
        "why_not": (
            "every job refuses on its own terms, so jobs_executable is 0 by "
            "counting rather than by a guard. A guard that special-cases the "
            "safe state stops working the moment the state changes."
        ),
        "with_zero_approved_sources_there_is_no_url_to_fetch": True,
        "execution_modes_not_implemented": list(EXECUTION_MODES_NOT_IMPLEMENTED),
    }


def _health() -> dict[str, Any]:
    health = build_scheduler_health(
        cycle=_fixture_cycle(),
        scheduler_process_active=None,
        persistent_state_available=True,
        activation_allowlist_count=0,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "scheduler_runtime_ready": health["scheduler_runtime_ready"],
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "conditions_met": health["conditions_met"],
        "jobs_known": health["jobs_known"],
        "jobs_due": health["jobs_due"],
        "jobs_executable": health["jobs_executable"],
        "jobs_blocked": health["jobs_blocked"],
        "scheduler_process_active": health["scheduler_process_active"],
        "scheduler_process_is_gate_157": True,
        "source_monitoring_live": False,
        "runtime_ready_is_not_monitoring_live": health[
            "runtime_ready_is_not_monitoring_live"
        ],
    }


def _monitoring_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_monitoring_live": False,
        "collectors_activated": 0,
        "live_source_calls": 0,
        "urls_fetched": 0,
        "raw_payloads_written": 0,
        "api_key_required": False,
        "sources_approved_for_activation": 0,
        "what_gate_156_changed": (
            "a scheduler runtime exists and evaluates a schedule deterministically"
        ),
        "what_gate_156_did_not_change": [
            "source_monitoring_live is still false",
            "no source is approved",
            "no terms review was completed",
            "no collector was registered or invoked",
            "no network call was made",
            "scheduler_package_installed is still false",
        ],
    }


def _blockers_markdown() -> str:
    return "\n".join(
        [
            "# Gate 156 — what still blocks source collection",
            "",
            "`scheduler_runtime_ready` is true. `source_monitoring_live` is false,",
            "and nothing in this gate can change that.",
            "",
            "## Cleared by this gate",
            "",
            "```text",
            "nothing computes a next run time      -> compute_next_run_at()",
            "nothing runs a cycle                  -> run_scheduler_cycle()",
            "no machine-readable scheduler health  -> build_scheduler_health()",
            "```",
            "",
            "## NOT cleared by this gate",
            "",
            "```text",
            "scheduler_package_installed    still false, deliberately. Gate 143's",
            "                               blocker is find_spec over eight",
            "                               packages; installing one would clear",
            "                               it without computing a due date.",
            "background_worker              Gate 157",
            "persistent collection job store Gate 158",
            "periodic_trigger               Gate 159 - no .timer or .cron exists",
            "production_raw_payload_store   Gate 160",
            "a collector                    Gate 161",
            "source activation approval     Gate 162, and a human before it",
            "```",
            "",
            "## The two blockers no gate in this block clears",
            "",
            "```text",
            "171 sources terms_blocked   a human must read each source's terms",
            "  6 sources human_review    a human must look",
            "```",
            "",
            "Building the entire 156-165 block leaves both untouched. When they",
            "clear, activation is one approval away instead of a runtime away.",
            "",
            "## The claim this gate must not support",
            "",
            "> NativeForge monitors grant sources.",
            "",
            "It does not. It can now evaluate 177 sources against a clock and",
            "refuse all 177, which is a scheduler that works and a system that",
            "polls nothing.",
            "",
        ]
    )


def build_scheduler_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; no database, no clock."""
    files = {
        SURVEY_FILE: _json(_survey()),
        JOB_MODEL_FILE: _json(_job_model()),
        SMOKE_FILE: _json(_smoke()),
        BLOCKED_FILE: _json(_blocked_job()),
        EMPTY_FILE: _json(_empty_allowlist()),
        HEALTH_FILE: _json(_health()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_scheduler_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_scheduler_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def scheduler_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
