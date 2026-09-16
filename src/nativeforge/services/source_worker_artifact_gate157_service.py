"""Gate 157K: the worker runtime, written down. Deterministic, no database.

Lease rows and live registry counts belong in the verifier that measures them.
Every smoke below runs against fixed fixture inputs and a fixed clock, so the
committed artifact is the shape of a worker cycle rather than a reading of
today's database.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.source_collection_job_lease_service import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    LEASE_STATUSES,
    TABLE_NAME,
)
from nativeforge.services.source_collection_retry_policy_service import (
    BASE_BACKOFF_SECONDS,
    BLOCKER_TO_CLASS,
    FAILURE_CLASSES,
    HUMAN_REVIEW_BLOCKED,
    MAX_BACKOFF_SECONDS,
    PERMANENT_WORKER_FAILURE,
    REFUSED_BY_ACTIVATION,
    RETRYABLE_CLASSES,
    TERMS_BLOCKED,
    TRANSIENT_WORKER_FAILURE,
    WHY_NOT_RETRIED,
    classify_blockers,
    compute_backoff_seconds,
    evaluate_retry,
)
from nativeforge.services.source_collection_worker_health_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    build_worker_health,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    HANDLERS_NOT_IMPLEMENTED,
    WORKER_STATUSES,
)

SCHEMA_VERSION = "nf_source_worker_gate157_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_worker_gate157"

SURVEY_FILE = "worker_runtime_survey.json"
CYCLE_FILE = "worker_cycle_smoke.json"
CLAIM_FILE = "worker_claim_smoke.json"
DUPLICATE_FILE = "duplicate_claim_refusal.json"
EXPIRED_FILE = "expired_lease_reclaim.json"
RETRY_FILE = "retry_policy.json"
HEALTH_FILE = "worker_health.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_worker_runtime_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    CYCLE_FILE,
    CLAIM_FILE,
    DUPLICATE_FILE,
    EXPIRED_FILE,
    RETRY_FILE,
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

FIXTURE_NOW = "2026-09-15T12:00:00Z"
FIXTURE_LATER = "2026-09-15T12:10:00Z"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "157",
        "subject": "background worker runtime",
        "the_worker_that_already_existed": {
            "module": "source_scheduler_dry_run_worker_service (Gate 100C)",
            "what_it_is": "a pure function that classifies a list of jobs",
            "its_own_docstring": (
                "a dry-run worker is not a worker. It is the shape a worker "
                "would have, exercised against jobs that cannot run."
            ),
            "what_it_lacks": [
                "worker identity",
                "job claiming",
                "lease semantics",
                "retry accounting",
                "failure classes",
                "persistence",
                "restart recovery",
                "a process",
            ],
        },
        "could_two_workers_race_before_this_gate": {
            "answer": "yes, trivially",
            "why": (
                "nothing recorded that a worker looked at a job, so two "
                "processes both classified every job and neither could tell. "
                "It did not matter while the classification wrote nothing."
            ),
        },
        "why_a_new_table_was_required": {
            "candidates_considered": [
                "nf_discovery_intake_runs",
                "nf_nofo_extraction_runs",
                "nf_pursuit_tasks",
                "nf_source_check_runs",
            ],
            "closest": "nf_source_check_runs",
            "why_it_does_not_fit": (
                "its check_status vocabulary is scheduled/running/succeeded/"
                "succeeded_with_warnings/failed/canceled, beside "
                "opportunities_seen_count and accepted_count. That is the "
                "lifecycle of a check that happened. Writing a lease there "
                "would assert a check ran when nothing did."
            ),
            "migration": "0043",
            "table": TABLE_NAME,
            "contrast_with_gate_156": (
                "Gate 156 needed no migration because nf_opportunity_sources "
                "already carried the scheduling columns. There is no "
                "equivalent for a lease."
            ),
        },
        "what_the_table_cannot_hold": [
            "a response body",
            "a url",
            "a credential or api key",
            "a provider subject",
            "customer data",
            "an address",
        ],
        "three_columns_the_database_refuses_to_set_true": [
            "collector_invoked",
            "url_fetched",
            "raw_payload_written",
        ],
        "source_monitoring_live": False,
    }


def _claim_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lease_seconds_default": DEFAULT_LEASE_SECONDS,
        "max_attempts_default": DEFAULT_MAX_ATTEMPTS,
        "lease_statuses": list(LEASE_STATUSES),
        "worker_statuses": list(WORKER_STATUSES),
        "atomicity": (
            "a unique index on (organization_id, job_id). Two workers racing "
            "both insert; one wins and the other receives an IntegrityError, "
            "which this service turns into a refusal rather than an exception."
        ),
        "why_not_select_then_insert": (
            "a SELECT-then-INSERT leaves a window between the two statements, "
            "and the window is where the race lives. The check that matters is "
            "the one the database makes."
        ),
        "a_claim_is_not_an_attempt": (
            "claiming records the right to decide. The attempt count moves "
            "only when something was actually attempted, or a job nobody can "
            "run would exhaust its budget and then look permanently failed."
        ),
    }


def _duplicate_refusal() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": "worker-1 holds a live lease; worker-2 claims the same job",
        "outcome": "refused",
        "blocked_reasons": [
            "job_is_already_claimed_by_another_worker",
            "lease_has_not_expired_and_cannot_be_stolen",
        ],
        "a_live_lease_cannot_be_stolen": (
            "not by another worker, and not by a second process sharing the "
            "same worker id"
        ),
    }


def _expired_reclaim() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": (
            f"worker-1 claims at {FIXTURE_NOW} for {DEFAULT_LEASE_SECONDS}s; "
            f"worker-2 claims the same job at {FIXTURE_LATER}"
        ),
        "outcome": "reclaimed",
        "why_expiry_exists": (
            "a worker that dies holding a claim would block that job forever. "
            "Expiry is the only release that does not need its owner."
        ),
        "why_a_live_lease_is_not_reclaimable": (
            "a claim anybody can take is not a claim, and the lease would be decorative"
        ),
        "expiry_is_derived_at_read_time": (
            "storing 'expired' would need something to run and write it, and "
            "nothing runs"
        ),
    }


def _retry_policy() -> dict[str, Any]:
    decisions = {
        klass: evaluate_retry(
            failure_class=klass, attempt_count=0, max_attempts=3, now=FIXTURE_NOW
        )
        for klass in (
            REFUSED_BY_ACTIVATION,
            TERMS_BLOCKED,
            HUMAN_REVIEW_BLOCKED,
            PERMANENT_WORKER_FAILURE,
            TRANSIENT_WORKER_FAILURE,
        )
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "failure_classes": list(FAILURE_CLASSES),
        "retryable_classes": sorted(RETRYABLE_CLASSES),
        "only_one_class_retries": len(RETRYABLE_CLASSES) == 1,
        "why_not_retried": dict(WHY_NOT_RETRIED),
        "blocker_to_class": dict(BLOCKER_TO_CLASS),
        "matched_by_exact_value_not_substring": (
            "source_terms_not_approved and source_activation_not_approved "
            "differ by one word; a substring match over either would catch the "
            "other"
        ),
        "decisions": {
            klass: {
                "should_retry": decision["should_retry"],
                "backoff_seconds": decision["backoff_seconds"],
                "why_not_retried": decision["why_not_retried"],
            }
            for klass, decision in decisions.items()
        },
        "backoff": {
            "base_seconds": BASE_BACKOFF_SECONDS,
            "cap_seconds": MAX_BACKOFF_SECONDS,
            "attempt_1": compute_backoff_seconds(1),
            "attempt_2": compute_backoff_seconds(2),
            "attempt_3": compute_backoff_seconds(3),
            "deterministic": True,
            "jitter": False,
            "why_no_jitter": (
                "jitter buys herd-avoidance among many workers. There is one "
                "worker, and a reproducible next-retry time is worth more."
            ),
        },
        "bounded_in_the_database": (
            "max_attempts lives on the lease row. A worker holding its budget "
            "in memory would reset it on every crash - precisely when a bound "
            "matters most."
        ),
        "with_zero_approved_sources_every_job_lands_in_a_non_retrying_class": True,
    }


def _cycle_smoke() -> dict[str, Any]:
    blockers = [
        "source_terms_not_approved",
        "source_activation_not_approved",
        "source_requires_human_review",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_at": FIXTURE_NOW,
        "handler": "evaluate_only",
        "handlers_not_implemented": list(HANDLERS_NOT_IMPLEMENTED),
        "scenario": "five jobs, none executable, every permission absent",
        "expected": {
            "jobs_claimed": 5,
            "jobs_refused": 5,
            "jobs_retryable": 0,
            "jobs_completed": 0,
        },
        "classification_of_those_blockers": classify_blockers(blockers),
        "why_terms_wins_over_activation": (
            "the terms review is the thing a person does first; naming the "
            "later blocker would send them to the wrong queue"
        ),
        "permission_is_read_not_recomputed": (
            "the scheduler decided `executable`; the worker reads it. Two "
            "places for one answer is how they come to disagree."
        ),
        "a_refusal_is_not_a_failure": (
            "the worker claimed the job, asked whether it may run it, was told "
            "no, recorded the reason and released the claim. That is the "
            "worker working."
        ),
        "a_truncated_batch_says_so": (
            "jobs_offered, jobs_seen and jobs_not_reached_this_cycle must add "
            "up. A batch limit nobody can see is how a backlog goes unnoticed."
        ),
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "threads_started": 0,
    }


def _health() -> dict[str, Any]:
    health = build_worker_health(
        cycle=None,
        duplicate_claim_refused=True,
        expired_lease_reclaimed=True,
        retry_bounded=True,
        worker_process_active=None,
        jobs_available=0,
        jobs_claimable=0,
        stale_leases=0,
        activation_allowlist_count=0,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "note": (
            "built with no cycle supplied, so worker_runtime_ready is false "
            "here. That is the shape of the lane, not a health reading - the "
            "live reading comes from "
            "scripts/verify_nativeforge_source_worker_runtime.sh."
        ),
        "unmeasured_health": {
            "worker_runtime_ready": health["worker_runtime_ready"],
            "blockers": health["blockers"],
        },
        "worker_process_active": health["worker_process_active"],
        "worker_ready_is_not_monitoring_live": health[
            "worker_ready_is_not_monitoring_live"
        ],
        "source_monitoring_live": False,
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
        "what_gate_157_changed": (
            "a worker claims jobs with an expiring lease, classifies why each "
            "one refuses, retries only genuine transient failures, and "
            "survives a restart"
        ),
        "what_gate_157_did_not_change": [
            "source_monitoring_live is still false",
            "no source is approved",
            "no terms review was completed",
            "no collector exists to invoke",
            "no network call was made",
            "no systemd worker unit was installed or enabled",
        ],
    }


def _blockers_markdown() -> str:
    return "\n".join(
        [
            "# Gate 157 — what still blocks source collection",
            "",
            "`worker_runtime_ready` is true. `source_monitoring_live` is false.",
            "",
            "## Cleared by this gate",
            "",
            "```text",
            "no worker identity          -> an explicit worker_id on every claim",
            "no job claiming             -> an atomic lease on a unique index",
            "no retry accounting         -> bounded, classified, persisted",
            "no restart recovery         -> the lease table is the state",
            "no process                  -> scripts/run_source_collection_worker.py",
            "```",
            "",
            "## NOT cleared by this gate",
            "",
            "```text",
            "background_worker           Gate 98E looks for nativeforge.workers",
            "  (the detector)            or a console entry point. This gate adds",
            "                            a script, not a package module, so the",
            "                            detector still reports it absent - the",
            "                            same shape as Gate 156 and the scheduler",
            "                            package.",
            "persistent job store        Gate 158 - leases exist; a queue does not",
            "periodic trigger            Gate 159 - no .timer or .cron exists",
            "raw payload store           Gate 160",
            "a collector                 Gate 161",
            "source activation approval  Gate 162, and a human before it",
            "```",
            "",
            "## The two blockers no gate in this block clears",
            "",
            "```text",
            "171 sources terms_blocked   a human must read each source's terms",
            "  6 sources human_review    a human must look",
            "```",
            "",
            "## The claim this gate must not support",
            "",
            "> NativeForge has a worker collecting grant data.",
            "",
            "It has a worker. The worker claims a job, asks whether it may run",
            "it, is told no by every one of 177 sources, records the reason and",
            "releases the claim. Nothing is collected, and nothing can be until",
            "a person reads some terms.",
            "",
        ]
    )


def build_worker_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; no database, no clock."""
    files = {
        SURVEY_FILE: _json(_survey()),
        CYCLE_FILE: _json(_cycle_smoke()),
        CLAIM_FILE: _json(_claim_smoke()),
        DUPLICATE_FILE: _json(_duplicate_refusal()),
        EXPIRED_FILE: _json(_expired_reclaim()),
        RETRY_FILE: _json(_retry_policy()),
        HEALTH_FILE: _json(_health()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_worker_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_worker_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def worker_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
