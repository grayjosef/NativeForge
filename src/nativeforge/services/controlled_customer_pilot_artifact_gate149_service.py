"""Gate 149G: the pilot activation package, written down.

Deterministic: reads no database and takes no arguments. What is committed is
the part that does not move — the nine prerequisites, what a pilot would and
would not unlock, the capabilities that stay separately gated, and the bundled
requests that are refused. Live values belong in the verifier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.controlled_customer_pilot_activation_boundary_service import (  # noqa: E501
    ACTIVATION_APPROVAL_FIELDS,
    BUNDLE_TARGETS,
    UNSAFE_BUNDLE_KEYS,
)
from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    NO_GO,
    NOT_APPROVED,
    PREREQUISITE_OWNERS,
    PREREQUISITES,
    SEPARATELY_GATED,
    WOULD_NOT_UNLOCK,
    WOULD_UNLOCK,
)

SCHEMA_VERSION = "nf_controlled_customer_pilot_gate149_artifacts_v1"

ARTIFACT_DIR = "artifacts/controlled_customer_pilot_gate149"

SURVEY_FILE = "pilot_activation_survey.json"
CHECKLIST_FILE = "pilot_activation_checklist.json"
DRY_RUN_FILE = "pilot_activation_dry_run_decision.json"
BLOCKERS_FILE = "pilot_activation_blockers.json"
BUNDLED_FILE = "unsafe_bundled_requests.json"
COCKPIT_FILE = "cockpit_pilot_activation_status.json"
READINESS_FILE = "pilot_activation_readiness.json"
NEXT_ACTION_FILE = "next_pilot_activation_human_actions.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    CHECKLIST_FILE,
    DRY_RUN_FILE,
    BLOCKERS_FILE,
    BUNDLED_FILE,
    COCKPIT_FILE,
    READINESS_FILE,
    NEXT_ACTION_FILE,
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

STAYS_FALSE: tuple[str, ...] = (
    "controlled_customer_pilot",
    "production_rollout",
    "customer_auth_live",
    "verified_operational_binding",
    "consent_boundary_documented",
    "customer_beta_scope_approved",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"forbidden shape {shape!r} in {name}")


def _survey() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "question": "what must be true before a controlled customer pilot starts?",
        "answer": "nine prerequisites, one of which is a customer",
        "controlled_customer_pilot": False,
        "the_finding": (
            "controlled_customer_pilot is not a value that is false. It is not "
            "a value at all: no table records a pilot approval, no environment "
            "flag exists, and no code path sets it true. Every occurrence is a "
            "literal False written into a response."
        ),
        "why_that_matters": (
            "a reader given prerequisites assumes satisfying them flips a "
            "switch, and goes looking for it. There isn't one, and building "
            "one before its prerequisites exist is how one gets flipped early."
        ),
        "dead_go_branches_left_alone": (
            "several older assembler services hardcode a NO_GO status and then "
            "branch on == GO. Read as code those branches are dead; read as "
            "policy they are the deliberate modelling gate Gate 115 described. "
            "Rewriting them to be reachable would manufacture the switch this "
            "gate declined to build."
        ),
        "no_route_can_activate_a_pilot": True,
        "no_table_records_a_pilot_approval": True,
        "no_environment_flag_exists": True,
        "not_approved": list(NOT_APPROVED),
    }


def _checklist() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "prerequisites": [
            {"prerequisite": name, **PREREQUISITE_OWNERS[name]}
            for name in PREREQUISITES
        ],
        "prerequisite_count": len(PREREQUISITES),
        "already_satisfied": ["customer_data_write_guard_ready"],
        "would_unlock": list(WOULD_UNLOCK),
        "would_not_unlock": list(WOULD_NOT_UNLOCK),
        "activation_package_ready": True,
        "package_ready_is_not_an_activated_pilot": (
            "activation_package_ready says the prerequisites are stated and "
            "measurable; controlled_customer_pilot says a pilot is running"
        ),
    }


def _dry_run() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "may_activate": False,
        "may_activate_is_always_false": True,
        "why": (
            "no mechanism exists to record a pilot activation. "
            "prerequisites_would_permit answers the question worth asking; "
            "may_activate answers whether anything could act on it."
        ),
        "mutation_enabled": False,
        "mutation_performed": False,
        "rows_written": 0,
        "connection_supplied": False,
        "takes_no_connection": True,
        "imports_no_repository": True,
        "activation_approval_fields_required": list(ACTIVATION_APPROVAL_FIELDS),
        "permitted_prerequisites_branch_reachable": True,
        "permitted_branch_still_activates_nothing": True,
    }


def _blockers() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "controlled_customer_pilot": False,
        "blockers": [
            {"prerequisite": name, **PREREQUISITE_OWNERS[name]}
            for name in PREREQUISITES
            if name != "customer_data_write_guard_ready"
        ],
        "front_of_the_queue": dict(
            PREREQUISITE_OWNERS["real_customer_organization_exists"]
        ),
        "cheapest_outstanding": dict(
            PREREQUISITE_OWNERS["support_and_rollback_owner_named"]
        ),
        "stays_false_after_this_gate": list(STAYS_FALSE),
    }


def _bundled() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "unsafe_bundle_keys": list(UNSAFE_BUNDLE_KEYS),
        "bundle_targets": dict(BUNDLE_TARGETS),
        "separately_gated": {
            name: dict(entry) for name, entry in SEPARATELY_GATED.items()
        },
        "refused_even_when_every_prerequisite_is_met": True,
        "why": (
            "a pilot that quietly turned on email because a pilot obviously "
            "needs notifications would undo four gates in one sentence. Being "
            "allowed to start a pilot is not being allowed to start anything "
            "else."
        ),
        "each_bundled_request_names_its_target": True,
    }


def _cockpit_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "controlled_customer_pilot",
        "status": "PRODUCTION_FALSE",
        "value": False,
        "operational": False,
        "pilot_active": False,
        "production_ready": False,
        "what_changed_in_gate_149": (
            "the lane said the pilot was not approved, which is true and "
            "invites a reader to look for the approval. It now says there are "
            "eight prerequisites outstanding, one of which is a customer, and "
            "that no mechanism exists to record an activation."
        ),
        "email_included": False,
        "source_monitoring_included": False,
        "object_storage_included": False,
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "activation_package_ready": True,
        "controlled_customer_pilot": False,
        "pilot_activation_allowed": False,
        "mutation_path_enabled": False,
        "activation_mechanism_exists": False,
        "production_rollout": NO_GO,
        "production_is_never_computed": True,
        "prerequisite_count": len(PREREQUISITES),
        "separately_gated": sorted(SEPARATELY_GATED),
        "separately_gated_are_not_pilot_blockers": True,
        "stays_false_after_this_gate": list(STAYS_FALSE),
        "rows_written": 0,
        "real_organization_touched": False,
    }


def _next_action_markdown() -> str:
    lines = [
        "# Gate 149 — the next pilot activation actions",
        "",
        "`controlled_customer_pilot` is false, and there is nothing to set it",
        "with: no table records a pilot approval, no flag exists, and no code",
        "path assigns it. This gate states the package and builds no switch.",
        "",
        "## The nine prerequisites",
        "",
        "```text",
    ]
    for name in PREREQUISITES:
        owner = PREREQUISITE_OWNERS[name]
        lines.append(name)
        lines.append(f"    kind    {owner['kind']}")
        lines.append(f"    owner   {owner['owner']}")
        lines.append(f"    gate    {owner['gate']}")
    lines += [
        "```",
        "",
        "One is satisfied: the customer data write guard, from Gate 148.",
        "",
        "## The order",
        "",
        "```text",
        "1  a real customer organization has to exist",
        "     the front of the queue for the third gate running, and the only",
        "     item no approval can supply",
        "",
        "2  the second-person invite event                  Gate 146",
        "3  the verified binding approval                   Gate 147",
        "4  the consent document, then a consent record     Gate 148",
        "5  the customer beta scope approval                Gate 145",
        "6  name a support and rollback owner               cheap; do it early",
        "7  an owner accepts the pilot scope limitations",
        "8  then decide how a pilot activation is recorded",
        "```",
        "",
        "Item 6 is one decision and two names, and a pilot without a named",
        "owner is a pilot whose first incident has no addressee.",
        "",
        "## What a pilot would unlock",
        "",
        "```text",
    ]
    lines += [f"- {entry}" for entry in WOULD_UNLOCK]
    lines += [
        "```",
        "",
        "## What it would not",
        "",
        "```text",
    ]
    lines += [f"- {entry}" for entry in WOULD_NOT_UNLOCK]
    lines += [
        "```",
        "",
        "## What may never be bundled with it",
        "",
        "```text",
    ]
    for name, entry in SEPARATELY_GATED.items():
        lines.append(f"{name:28s} gate {entry['gate']}")
        lines.append(f"{'':28s} {entry['why_separate']}")
    lines += [
        "```",
        "",
        "Refused even when every prerequisite is satisfied.",
        "",
        "## What stays false",
        "",
        "```text",
    ]
    lines += [f"{name}   false" for name in STAYS_FALSE]
    lines += [
        "```",
        "",
        "This gate assembled the package. It activated nothing.",
        "",
    ]
    return "\n".join(lines)


def build_pilot_activation_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        CHECKLIST_FILE: _json(_checklist()),
        DRY_RUN_FILE: _json(_dry_run()),
        BLOCKERS_FILE: _json(_blockers()),
        BUNDLED_FILE: _json(_bundled()),
        COCKPIT_FILE: _json(_cockpit_status()),
        READINESS_FILE: _json(_readiness()),
        NEXT_ACTION_FILE: _next_action_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_pilot_activation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_pilot_activation_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def pilot_activation_artifact_invariant_failures(
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
