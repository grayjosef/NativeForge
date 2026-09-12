"""Gate 148H: the consent and customer data boundary, written down.

Deterministic: reads no database and takes no arguments. What is committed is
the part that does not move — the nine classes, what consent requires, what is
not consent, and the blocker stack. Live values belong in the verifier.

No example address, no long digit string, no document body. Every file is
scanned before it is returned and the builder raises rather than writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.customer_beta_consent_boundary_service import (
    BETA_SCOPE_APPROVAL_FIELDS,
    BLOCKER_OWNERS,
    CONSENT_ABSENT,
    CONSENT_RECORD_FIELDS,
    INFERRED_CONSENT_KEYS,
    NO_REAL_CUSTOMER_ORG,
    NOT_APPROVED,
    SCOPE_ABSENT,
)
from nativeforge.services.customer_data_classification_service import (
    ADDITIONAL_ACTIVATION_REQUIRED,
    CUSTOMER_DATA_CLASSES,
    DATA_CLASSES,
    NEVER_STORED_CLASSES,
    NOT_CONSENT,
    PRE_CONSENT_CLASSES,
    build_data_class_catalogue,
)
from nativeforge.services.customer_data_write_guard_service import CONTROLLED_SCOPE

SCHEMA_VERSION = "nf_customer_data_boundary_gate148_artifacts_v1"

ARTIFACT_DIR = "artifacts/customer_data_boundary_gate148"

SURVEY_FILE = "customer_data_boundary_survey.json"
CLASSES_FILE = "customer_data_classes.json"
CONSENT_FILE = "consent_boundary_checklist.json"
SCOPE_FILE = "beta_scope_approval_checklist.json"
GUARD_FILE = "data_write_guard_smoke.json"
COCKPIT_FILE = "cockpit_customer_data_boundary_status.json"
READINESS_FILE = "customer_data_boundary_readiness.json"
NEXT_ACTION_FILE = "next_customer_data_boundary_human_action.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    CLASSES_FILE,
    CONSENT_FILE,
    SCOPE_FILE,
    GUARD_FILE,
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
    "consent_boundary_documented",
    "customer_beta_scope_approved",
    "customer_auth_live",
    "verified_operational_binding",
    "controlled_customer_pilot",
    "production_rollout",
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
        "question": "may customer data be written, and has anybody agreed to it?",
        "answer": "no, and no record of agreement exists anywhere",
        "consent_boundary_documented": False,
        "customer_beta_scope_approved": False,
        "consent_table_in_any_migration": False,
        "consent_service_before_this_gate": False,
        "the_finding": (
            "every post-award repository gates a production write on exactly "
            "customer_auth_live and verified_operational_binding. Both are "
            "identity facts. Neither is consent - so on the day Gates 146 and "
            "147 make both true, a production customer write becomes permitted "
            "with no consent recorded anywhere."
        ),
        "why_the_boundary_comes_first": (
            "it has to exist before those lanes turn, not after"
        ),
        "what_protects_data_today": [
            "the post-award routes force fact_status=demo_fixture and refuse a "
            "caller-supplied label",
            "object_store_configured is false, so document bodies are refused",
            "the delivery table has a recipient fingerprint and domain and no "
            "column for an address",
            "source_monitoring_live is false, so no collector runs",
        ],
        "why_that_is_not_a_boundary": (
            "each is a capability being off, which is a different thing from a "
            "boundary, and each disappears the moment its capability is on"
        ),
        "existing_vocabulary": {
            "fact_status": ["demo_fixture", "tenant_supplied", "verified", "unknown"],
            "note": (
                "tenant_supplied is already permitted by every post-award CHECK "
                "constraint, so the schema is open to customer data; what keeps "
                "it out is that no write path chooses it"
            ),
        },
        "not_approved": list(NOT_APPROVED),
    }


def _consent_checklist() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "consent_boundary_documented": False,
        "record_fields_required": list(CONSENT_RECORD_FIELDS),
        "a_partial_record_is": "no record, not a weak one",
        "not_consent": [dict(entry) for entry in NOT_CONSENT],
        "inferred_consent_keys_refused_by_name": list(INFERRED_CONSENT_KEYS),
        "why_refused_by_name": (
            "an omission here would be read as permission; somebody offering a "
            "login as consent learns their reasoning was rejected"
        ),
        "blocker": CONSENT_ABSENT,
        "owner": dict(BLOCKER_OWNERS[CONSENT_ABSENT]),
        "what_has_to_be_decided_first": [
            "what NativeForge collects",
            "what it retains, and for how long",
            "what it exports",
            "how it deletes on request",
            "how a tenant withdraws agreement",
        ],
        "who_decides": "Mayhem writes it; each tenant agrees to it",
        "not_engineering": True,
    }


def _scope_checklist() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "customer_beta_scope_approved": False,
        "approval_fields_required": list(BETA_SCOPE_APPROVAL_FIELDS),
        "blocker": SCOPE_ABSENT,
        "owner": dict(BLOCKER_OWNERS[SCOPE_ABSENT]),
        "is_one_of": "the four approvals Gate 145 says the customer beta needs",
        "the_other_three": [
            "customer_auth_live",
            "verified_operational_binding",
            "consent_and_data_boundary_documented",
        ],
        "front_of_the_queue": dict(BLOCKER_OWNERS[NO_REAL_CUSTOMER_ORG]),
    }


def _guard_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "guard": "customer_data_write_guard_service.evaluate_write",
        "writes": False,
        "opens_a_connection": False,
        "rows_written": 0,
        "decisions": [
            {
                "case": "demo fixture, demo organization, controlled demo scope",
                "write_allowed": True,
                "why": "unchanged by this gate; the fixture lane is unaffected",
            },
            {
                "case": "customer data, demo organization, controlled demo scope",
                "write_allowed": False,
                "why": "customer data in the demo scope is the substitution "
                "this block exists to prevent",
            },
            {
                "case": "an unclassified data class",
                "write_allowed": False,
                "why": "deny by default; it cannot inherit permission from a "
                "neighbouring class",
            },
            {
                "case": "consent offered as a login, membership or invite",
                "write_allowed": False,
                "why": "refused by name rather than ignored",
            },
            {
                "case": "customer document body, object storage off",
                "write_allowed": False,
                "why": "consent does not substitute for the capability",
            },
            {
                "case": "customer recipient, email delivery off",
                "write_allowed": False,
                "why": "the same, for a different capability",
            },
            {
                "case": "a provider subject, everything else granted",
                "write_allowed": False,
                "why": "never stored; not a class anybody can agree to",
            },
            {
                "case": "the refused real organization, everything granted",
                "write_allowed": False,
                "why": "refused by name",
            },
            {
                "case": "a fixture customer organization, everything granted",
                "write_allowed": True,
                "why": "the permitted branch, kept reachable so every refusal "
                "above it stays falsifiable - and it still writes nothing",
            },
        ],
        "controlled_scope": CONTROLLED_SCOPE,
    }


def _cockpit_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lanes_added": ["consent_and_data_boundary", "customer_beta_scope"],
        "status": "REQUIRES_HUMAN_APPROVAL",
        "value": False,
        "operational": False,
        "production_ready": False,
        "customer_beta_approved": False,
        "what_changed": (
            "the cockpit had fifteen lanes and none of them was consent, so a "
            "reader could see customer auth and the verified binding false and "
            "take those for the last two things in the way. They are two of "
            "four."
        ),
        "demo_fixture_writes_still_allowed": True,
        "customer_data_writes_allowed": False,
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "consent_boundary_documented": False,
        "customer_beta_scope_approved": False,
        "customer_data_write_guard_ready": True,
        "guard_ready_is_not_permission": (
            "the guard being correct says a future write path has something "
            "right to call; it does not say any write is allowed"
        ),
        "data_classes": len(DATA_CLASSES),
        "customer_data_classes": sorted(CUSTOMER_DATA_CLASSES),
        "pre_consent_classes": sorted(PRE_CONSENT_CLASSES),
        "never_stored_classes": sorted(NEVER_STORED_CLASSES),
        "additional_activation_required": dict(ADDITIONAL_ACTIVATION_REQUIRED),
        "unknown_is_blocked": True,
        "stays_false_after_this_gate": list(STAYS_FALSE),
        "rows_written": 0,
        "real_organization_touched": False,
    }


def _next_action_markdown() -> str:
    lines = [
        "# Gate 148 — the next consent and data boundary action",
        "",
        "Two of the four approvals the controlled customer beta needs are",
        "recorded nowhere, and neither is a code change.",
        "",
        "```text",
        "consent_boundary_documented    false",
        "customer_beta_scope_approved   false",
        "```",
        "",
        "## The order",
        "",
        "```text",
        "1  a real customer organization has to exist",
        "     Gate 147's finding, and still the front of the queue. There is",
        "     none in this deployment other than the refused one.",
        "",
        "2  decide what NativeForge collects, retains, exports and deletes",
        "     a document, not a code change. Gate 142 declined to build a",
        "     consent model before this existed, and was right to: a record",
        "     that looks like agreement and is not would be worse than none.",
        "",
        "3  decide how a tenant records agreement, and how they withdraw it",
        "",
        "4  Mayhem approves the controlled customer beta scope",
        "",
        "5  a consent record per organization, with all ten fields",
        "```",
        "",
        "## What is not consent",
        "",
        "```text",
    ]
    for entry in NOT_CONSENT:
        lines.append(entry["looks_like_consent"])
        lines.append(f"    says       {entry['actually_says']}")
        lines.append(f"    but        {entry['why_not']}")
    lines += [
        "```",
        "",
        "All four become available as Gates 146 and 147 land, which is why they",
        "are refused by name rather than left unmentioned.",
        "",
        "## What stays allowed",
        "",
        "```text",
        "demo fixture writes to the demo organization, controlled demo scope",
        "synthetic test data in hermetic tests",
        "fingerprints and domain halves, never the value",
        "```",
        "",
        "## What stays false",
        "",
        "```text",
    ]
    lines += [f"{name}   false" for name in STAYS_FALSE]
    lines += [
        "```",
        "",
        "This gate built the boundary. It created no consent and approved",
        "nothing.",
        "",
    ]
    return "\n".join(lines)


def build_customer_data_boundary_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        CLASSES_FILE: _json(build_data_class_catalogue()),
        CONSENT_FILE: _json(_consent_checklist()),
        SCOPE_FILE: _json(_scope_checklist()),
        GUARD_FILE: _json(_guard_smoke()),
        COCKPIT_FILE: _json(_cockpit_status()),
        READINESS_FILE: _json(_readiness()),
        NEXT_ACTION_FILE: _next_action_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_customer_data_boundary_artifacts(
    *, repo_root: Any = None
) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_customer_data_boundary_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def customer_data_boundary_artifact_invariant_failures(
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
