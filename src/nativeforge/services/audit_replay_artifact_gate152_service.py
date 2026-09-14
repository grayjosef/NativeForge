"""Gate 152H: audit replay and the evidence ledger, written down.

Deterministic: reads no database and takes no arguments. Live counts belong in
the verifier; what is committed is the vocabulary, the chain, the defect this
gate found in the last one, and the gaps that remain open.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.audit_replay_readiness_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    MUST_STAY_FALSE,
)
from nativeforge.services.audit_replay_service import (
    LINK_AUDIT_EVENT,
    LINK_DELIVERY_INTENT,
    LINK_DIGEST_RECORD,
    LINK_PAYLOAD_HASH,
)
from nativeforge.services.evidence_ledger_service import (
    EVIDENCE_TYPES,
    EXCLUDED_SOURCES,
    TYPE_LIMITATIONS,
)
from nativeforge.services.evidence_status_vocabulary_service import (
    EVIDENCE_STATUSES,
    NON_PROVING_STATUSES,
    PROVING_STATUSES,
    build_vocabulary,
)

SCHEMA_VERSION = "nf_audit_replay_gate152_artifacts_v1"

ARTIFACT_DIR = "artifacts/audit_replay_gate152"

SURVEY_FILE = "audit_replay_survey.json"
VOCABULARY_FILE = "evidence_status_vocabulary.json"
DIGEST_SMOKE_FILE = "audit_replay_digest_smoke.json"
INTENT_SMOKE_FILE = "audit_replay_delivery_intent_smoke.json"
LEDGER_FILE = "evidence_ledger_summary.json"
GAPS_FILE = "legacy_delivery_intent_gaps.json"
READINESS_FILE = "audit_replay_readiness.json"
BLOCKERS_FILE = "next_audit_replay_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    VOCABULARY_FILE,
    DIGEST_SMOKE_FILE,
    INTENT_SMOKE_FILE,
    LEDGER_FILE,
    GAPS_FILE,
    READINESS_FILE,
    BLOCKERS_FILE,
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
    "production_audit_ready",
    "email_delivery",
    "source_monitoring_live",
    "object_store_configured",
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
        "question": "can this system replay what it recorded?",
        "answer": "two of three links already worked; the third now does",
        "the_measurement": {
            "intents_naming_a_digest": 85,
            "intents_whose_audit_event_resolves": 85,
            "intents_whose_digest_record_existed": 0,
            "digest_delivery_intent_recorded_events": 85,
        },
        "what_that_reframed": (
            "Gate 150 said intents name a digest nobody kept, which was true "
            "and was one link. The intents themselves are properly attributed: "
            "every audit_event_id resolves. The chain was two-thirds intact, "
            "and describing it as absent would understate the system as badly "
            "as calling it complete would overstate it."
        ),
        "why_status_is_per_link": (
            "every legacy intent is simultaneously linked_record_found on its "
            "audit link and legacy_gap on its digest link. One status per "
            "record would have to pick one and be wrong about the other."
        ),
        "join_direction": (
            "the intent points at the audit event; nf_audit_events has no "
            "digest_id or intent_id column. A replay looking for the link on "
            "the event would report a gap that is not there."
        ),
        "gate_151_defect": {
            "what": (
                "the persisted-digest delivery guard reported without enforcing"
            ),
            "why": (
                "record_delivery_intent gates its write on "
                "decision['storage_allowed'], which prepare_delivery_intent "
                "computes from its own blocked list and cannot know about "
                "persistence - it takes no connection, deliberately. Gate 151 "
                "appended digest_id_names_no_persisted_digest to the caller's "
                "list instead, so the reason appeared and the row was written."
            ),
            "why_it_shipped_looking_correct": (
                "Gate 151's verifier exercised digest_record_exists directly "
                "rather than driving record_delivery_intent end to end"
            ),
            "how_it_briefly_read_green_here": (
                "an invalid recipient fingerprint was refusing the write for "
                "an unrelated reason; fixing the fingerprint removed the real "
                "blocker and the unpersisted-digest intent was accepted"
            ),
            "reported_without_enforcing": True,
            "fixed_in_gate": "152",
            "the_fix": (
                "the merged verdict gates the write AND overrides the reported "
                "storage_allowed, so blocked_reasons, storage_allowed and "
                "rows_written all say the same thing"
            ),
            "lesson": "a blocker that gates nothing is a comment",
        },
        "scope": "controlled_dev_demo audit replay, not legal-grade audit",
    }


def _digest_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subject": "digest",
        "links_checked": [
            LINK_DIGEST_RECORD,
            LINK_PAYLOAD_HASH,
            LINK_DELIVERY_INTENT,
        ],
        "proved": [
            "a persisted digest reads back by organization and id",
            "the stored hash equals one recomputed over the stored payload",
            "a tampered payload fails verification",
            "a digest no intent names reads not_replayable, honestly",
            "an archived digest is still replayable by id",
        ],
        "refused": [
            "a digest that does not exist - missing_record, not fabricated",
            "another organization's digest - the same answer as absent",
            "the real organization, by name",
        ],
        "writes": 0,
        "fabricates": False,
    }


def _intent_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subject": "delivery_intent",
        "links_checked": [
            LINK_DELIVERY_INTENT,
            LINK_DIGEST_RECORD,
            LINK_PAYLOAD_HASH,
            LINK_AUDIT_EVENT,
        ],
        "fully_linked_chain": {
            LINK_DELIVERY_INTENT: "linked_record_found",
            LINK_DIGEST_RECORD: "linked_record_found",
            LINK_PAYLOAD_HASH: "hash_verified",
            LINK_AUDIT_EVENT: "linked_record_found",
        },
        "verifier_happy_path_uses_a_real_audit_event": {
            "value": True,
            "why": (
                "referencing a random audit id would be manufacturing a broken "
                "link and then congratulating the verifier for detecting it"
            ),
        },
        "dangling_audit_event_id": {
            "is_a_negative_test_case": True,
            "expected_status": "missing_record",
            "where": "the test suite, against a fixture - not the verifier",
        },
        "legacy_intent_status": "legacy_gap",
        "why_not_missing_record": (
            "it is not wrong; it was un-storable at the time"
        ),
        "writes": 0,
    }


def _ledger() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_types": list(EVIDENCE_TYPES),
        "type_limitations": {
            name: list(values) for name, values in TYPE_LIMITATIONS.items()
        },
        "excluded_sources": [dict(entry) for entry in EXCLUDED_SOURCES],
        "entry_fields": [
            "organization_id",
            "evidence_type",
            "record_id",
            "related_record_ids",
            "evidence_status",
            "is_proof",
            "payload_hash",
            "created_at",
            "fact_status",
            "is_demo",
            "replay_limitations",
        ],
        "overall_status_rule": "the weakest entry, never an average",
        "a_defect_found_building_it": {
            "what": (
                "a raw sa.text() read of a JSON column returns a str on "
                "SQLite; only the typed sa.Table path deserializes it"
            ),
            "effect": (
                "the ledger hashed the JSON string while the stored hash was "
                "over the parsed dict, and reported a sound digest as "
                "missing_record - a false negative in an audit ledger, which "
                "is the worst direction for this kind of error"
            ),
            "fix": (
                "read the payload through the repository that owns it, so the "
                "two paths agree by construction rather than by coincidence"
            ),
            "family": "Gate 151's DATE coercion - an untyped read diverging "
            "from the typed one",
        },
        "exposes": "counts, hashes, statuses and ids",
        "never_exposes": [
            "a recipient address",
            "a provider subject",
            "a rendered body",
            "a document body",
        ],
    }


def _gaps() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "what": "delivery intents whose digest was never persisted",
        "status": "legacy_gap",
        "backfilled": False,
        "why_not_backfilled": (
            "the digests cannot be reconstructed - the snapshots they were "
            "built from are not guaranteed unchanged, so a regenerated digest "
            "would be a digest for that period and not the one the intent "
            "referred to. Storing one would produce a record that looks like "
            "evidence and is not."
        ),
        "why_not_missing_record": (
            "a legacy gap is not an error. These intents recorded a real "
            "intention accurately; what they could not do was keep the thing "
            "they referred to, because there was nothing to keep it in."
        ),
        "remedy": (
            "new intents recorded against persisted digests. The count falls "
            "visibly as they are, and the verifier prints it on every run."
        ),
        "enforcement": {
            "flag": "require_persisted_digest",
            "enforced_end_to_end_since": "Gate 152",
            "default": False,
            "why_default_off": (
                "the existing intents predate the table and Gate 142's callers "
                "are correct as written; a blocker applied unconditionally "
                "would retroactively invalidate history that is not wrong"
            ),
        },
        "what_would_close_them": [
            "every live intent resolving to a persisted digest",
            "the legacy rows archived, or accepted as pre-table history",
            "the flag default flipped, in a change somebody reviews",
        ],
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "audit_replay_ready",
        "scope": "controlled_dev_demo",
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "must_stay_false": list(MUST_STAY_FALSE),
        "reporting_a_gap_is_a_condition": {
            "value": True,
            "why": (
                "a replay that quietly produced a digest for the legacy "
                "intents would score better on every other condition and be "
                "worthless. A backfill fails this lane rather than passing it."
            ),
        },
        "derived_not_supplied": True,
        "production_audit_ready": False,
        "production_is_never_computed": True,
        "what_this_does_not_mean": [
            "that this would satisfy an auditor or a court",
            "that any digest was delivered",
            "that any tenant read anything",
            "that the legacy gaps were closed",
            "that any real tenant's evidence exists",
        ],
        "stays_false_after_this_gate": list(STAYS_FALSE),
    }


def _blockers_markdown() -> str:
    lines = [
        "# Gate 152 — what audit replay still cannot do",
        "",
        "`audit_replay_ready` is true for `controlled_dev_demo`. That is a",
        "narrower claim than it sounds.",
        "",
        "## What it does not mean",
        "",
        "```text",
        "not  legal-grade or production audit    production_audit_ready false",
        "not  that any digest was delivered      email_delivery false",
        "not  that any tenant read anything      nothing records a view",
        "not  that the legacy gaps were closed   they are reported, not filled",
        "not  that real tenant evidence exists   no consent, no customer org",
        "```",
        "",
        "## The open gaps",
        "",
        "```text",
        "legacy delivery intents            reported as legacy_gap, never",
        "                                   backfilled",
        "no view or read event is recorded  out of scope, named so it is not",
        "                                   mistaken for something that exists",
        "award proof events not in ledger   a different subject; a later gate",
        "                                   should build its own ledger",
        "```",
        "",
        "## What Gate 152 fixed in Gate 151",
        "",
        "The persisted-digest delivery guard reported without enforcing. The",
        "reason appeared in `blocked_reasons` and the row was written anyway,",
        "because the write gates on a `storage_allowed` computed before the",
        "digest linkage is known.",
        "",
        "It shipped looking correct because Gate 151's verifier exercised the",
        "linkage function directly rather than driving the write path, and it",
        "briefly read green here because an invalid recipient fingerprint was",
        "refusing for an unrelated reason.",
        "",
        "`require_persisted_digest=True` is now enforced end to end, and",
        "`storage_allowed`, `blocked_reasons` and `rows_written` all agree.",
        "",
        "## What stays false",
        "",
        "```text",
    ]
    lines += [f"{name}   false" for name in STAYS_FALSE]
    lines += [
        "```",
        "",
        "## Next",
        "",
        "Gate 153 — operational backup and restore readiness. A restore path",
        "proved after real data exists is a restore path proved too late.",
        "",
    ]
    return "\n".join(lines)


def build_audit_replay_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    vocabulary = build_vocabulary()
    files = {
        SURVEY_FILE: _json(_survey()),
        VOCABULARY_FILE: _json(
            {
                **vocabulary,
                "statuses_total": len(EVIDENCE_STATUSES),
                "proving": sorted(PROVING_STATUSES),
                "non_proving": sorted(NON_PROVING_STATUSES),
            }
        ),
        DIGEST_SMOKE_FILE: _json(_digest_smoke()),
        INTENT_SMOKE_FILE: _json(_intent_smoke()),
        LEDGER_FILE: _json(_ledger()),
        GAPS_FILE: _json(_gaps()),
        READINESS_FILE: _json(_readiness()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_audit_replay_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_audit_replay_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def audit_replay_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
