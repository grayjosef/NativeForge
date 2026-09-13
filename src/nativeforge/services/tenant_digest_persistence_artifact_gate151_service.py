"""Gate 151H: digest persistence, written down.

Deterministic: reads no database and takes no arguments. What is committed is
the schema contract, the behaviours proved, and the blockers that remain. Live
counts belong in the verifier, which reads them at the moment somebody asks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.tenant_digest_records_repository import (
    CALLER_MAY_NOT_SET,
    FORBIDDEN_PAYLOAD_FIELDS,
    TABLE_NAME,
)
from nativeforge.services.tenant_digest_persistence_readiness_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    MUST_STAY_FALSE,
)
from nativeforge.services.tenant_digest_persistence_service import (
    CONTROLLED_SCOPE,
    HONESTY_FIELDS,
    REQUIRED_DIGEST_FIELDS,
)

SCHEMA_VERSION = "nf_tenant_digest_persistence_gate151_artifacts_v1"

ARTIFACT_DIR = "artifacts/tenant_digest_persistence_gate151"

SURVEY_FILE = "digest_persistence_survey.json"
SCHEMA_FILE = "digest_schema_contract.json"
ROUNDTRIP_FILE = "digest_repository_roundtrip.json"
ROUTE_FILE = "digest_route_smoke.json"
LINKAGE_FILE = "delivery_intent_digest_linkage.json"
HASH_FILE = "digest_hash_stability.json"
READINESS_FILE = "tenant_digest_persistence_readiness.json"
BLOCKERS_FILE = "next_digest_persistence_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    SCHEMA_FILE,
    ROUNDTRIP_FILE,
    ROUTE_FILE,
    LINKAGE_FILE,
    HASH_FILE,
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

#: Columns the table deliberately does not have.
ABSENT_COLUMNS: tuple[str, ...] = (
    "recipient",
    "recipient_email",
    "email",
    "address",
    "rendered_body",
    "body",
    "html",
    "document_body",
)

STAYS_FALSE: tuple[str, ...] = (
    "production_digest_persistence",
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
        "question": "can a delivery intent re-read the digest it names?",
        "answer_before_this_gate": "no, and none ever could",
        "the_measurement": (
            "71 delivery intents, all 71 naming a digest, and zero of those "
            "digests stored anywhere"
        ),
        "why_it_mattered": (
            "a tenant misses a deadline and asks what NativeForge told them. "
            "The intent could say a digest was queued with four items visible "
            "and two suppressed; the digest could say nothing, because it did "
            "not exist. For a product whose purpose is award compliance, that "
            "is the wrong half of the record to have kept."
        ),
        "what_already_worked": (
            "build_digest_id has been deterministic with no clock in it since "
            "Gate 142, so a records table could use it as a real key rather "
            "than inventing a surrogate"
        ),
        "migration": "0042",
        "table": TABLE_NAME,
        "scope": CONTROLLED_SCOPE,
    }


def _schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "table": TABLE_NAME,
        "migration": "0042",
        "key": "organization_id + digest_id, unique where archived_at IS NULL",
        "stored": {
            "the_digest": "digest_payload_json, normalized",
            "the_hash": "payload_sha256 over a canonical serialisation",
            "the_counts": [
                "items_total",
                "items_visible",
                "items_suppressed",
                "items_unchanged",
            ],
            "the_honesty_counts": list(HONESTY_FIELDS),
            "the_caveats": ["caveats_json", "blocked_reasons"],
            "the_labelling": ["is_demo", "fact_status"],
            "the_lifecycle": ["archived_at", "created_at", "updated_at"],
        },
        "not_stored": {
            "absent_columns": list(ABSENT_COLUMNS),
            "why": (
                "a column that does not exist cannot be filled by a later "
                "mistake. Gate 142 wrote the rule for the delivery queue and "
                "it applies one table upstream."
            ),
            "the_rendering": (
                "the payload is what the digest IS; the body is one rendering "
                "of it, for one channel, at one moment. A table holding "
                "something email-shaped is how a preview-only lane quietly "
                "becomes a delivery lane."
            ),
        },
        "constraints": {
            "counts_agree": "items_total >= items_visible + items_suppressed",
            "counts_non_negative": "all four, and the three honesty counts",
            "never_sent": "delivery_status <> 'sent'",
            "capabilities_off": [
                "NOT email_delivery_live",
                "NOT source_monitoring_live",
            ],
            "demo_is_fixture": "(NOT is_demo) OR fact_status = 'demo_fixture'",
            "hash_shape": "length(payload_sha256) = 64",
        },
        "caller_may_not_set": list(CALLER_MAY_NOT_SET),
        "organization_id_is_authoritative_not_forbidden": True,
        "forbidden_payload_fields": list(FORBIDDEN_PAYLOAD_FIELDS),
        "required_digest_fields": list(REQUIRED_DIGEST_FIELDS),
        "row_level_security": "org isolation policy on postgresql, as 0041",
    }


def _roundtrip() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proved": [
            "a digest persists and reads back by its id",
            "the stored hash equals a hash recomputed over the stored payload",
            "the four counts come back agreeing",
            "human review, unverified deadlines and unknown reporting burden "
            "survive",
            "the caveats and blocked reasons survive",
            "the labelling is derived from the organization, not the caller",
            "the record states the capabilities were off when it was written",
        ],
        "refused": [
            "persisting the same period twice",
            "counts that do not agree, before the database says so",
            "a payload carrying a recipient or a rendering",
            "a caller-supplied is_demo, fact_status or payload hash",
            "the real organization, by name",
            "a cross-org read, list or archive",
        ],
        "archive_is_a_state": {
            "archived_row_readable_by_id": True,
            "archived_row_in_the_live_list": False,
            "why": (
                "an audit of a missed deadline needs the digest that was "
                "current at the time, not only the current one"
            ),
            "archiving_twice_refused": True,
        },
        "a_dialect_split_found_and_fixed": {
            "what": (
                "period_start and period_end are DATE columns and the digest "
                "carries ISO strings"
            ),
            "why_it_mattered": (
                "SQLite refuses a string outright and Postgres coerces it, so "
                "the insert would have passed in one environment and failed in "
                "the other - the same split Gate 142 hit when an untyped "
                "column bound a UUID on one dialect and not the other"
            ),
            "fix": "explicit coercion in the repository",
        },
    }


def _route_smoke() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "routes": [
            "POST   /v1/nf/demo/orgs/{org}/digest/persist",
            "GET    /v1/nf/demo/orgs/{org}/digest/records",
            "GET    /v1/nf/demo/orgs/{org}/digest/records/{digest_id}",
            "POST   /v1/nf/demo/orgs/{org}/digest/records/{digest_id}/archive",
        ],
        "unauthenticated": 401,
        "forged_dev_header": 401,
        "caller_supplied_label": 422,
        "missing_record": 404,
        "listing_omits_the_payload": {
            "value": True,
            "why": (
                "the payload is available by id; a list of them would make a "
                "listing route the largest response in the API"
            ),
        },
        "real_organization_route": None,
        "email_sent": False,
        "live_source_called": False,
        "object_store_contacted": False,
    }


def _linkage() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "the_question": "does the digest a delivery intent names actually exist?",
        "answerable_before_this_gate": False,
        "measured_always": "digest_record_persisted, on every record_delivery_intent",
        "enforced_opt_in": "require_persisted_digest=True adds a blocker",
        "why_opt_in": (
            "the 71 existing intents predate the table, and a blocker applied "
            "unconditionally would retroactively invalidate history that is "
            "not wrong, only un-storable at the time. Gate 142's callers pass "
            "no persisted digest and are correct as written."
        ),
        "blocker_when_enforced": "digest_id_names_no_persisted_digest",
        "linkage_is_org_scoped": True,
        "absent_table_answers_false_rather_than_raising": {
            "value": True,
            "why": (
                "an older database is an environment fact, not a caller "
                "defect; an intent recorded against one should get 'no "
                "persisted digest', not a stack trace"
            ),
        },
        "legacy_intents_are_not_backfilled": {
            "value": True,
            "why": (
                "the digests they named cannot be reconstructed - the "
                "snapshots they were built from are not guaranteed unchanged. "
                "Manufacturing a digest for a past intent would produce a "
                "record that looks like evidence and is not."
            ),
        },
    }


def _hash_stability() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm": "sha256 over json.dumps(payload, sort_keys, compact)",
        "stable_over": ["key order", "whitespace"],
        "different_payload_hashes_differently": True,
        "what_it_proves": (
            "a given rendering came from this stored digest, without the "
            "rendering being kept"
        ),
        "verify_rendering": {
            "matching_payload": "verified",
            "different_payload": "payload_hash_mismatch",
            "body_stored": False,
        },
        "digest_id_is_separately_deterministic": {
            "formula": "sha256(tenant_id|cadence|period_start|period_end)",
            "clock_free": True,
            "since": "Gate 142, which fixed an assembler that passed no period "
            "and produced an identical id every week",
        },
    }


def _readiness() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lane": "tenant_digest_persistence_live",
        "scope": CONTROLLED_SCOPE,
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "must_stay_false": list(MUST_STAY_FALSE),
        "derived_not_supplied": True,
        "production_digest_persistence": False,
        "production_is_never_computed": True,
        "what_this_does_not_mean": [
            "that any digest was sent",
            "that any live source was called",
            "that any real tenant's digest was stored",
            "that production digest persistence is available",
        ],
        "stays_false_after_this_gate": list(STAYS_FALSE),
    }


def _blockers_markdown() -> str:
    lines = [
        "# Gate 151 — what digest persistence still does not do",
        "",
        "`tenant_digest_persistence_live` is true for `controlled_dev_demo`.",
        "That is a narrower claim than it sounds, and the narrowness is the",
        "point.",
        "",
        "## What it does not mean",
        "",
        "```text",
        "not  that any digest was sent            email_delivery is false",
        "not  that any live source was called     source_monitoring_live false",
        "not  that a real tenant's digest exists  no consent, no customer org",
        "not  that production persistence works   never computed",
        "```",
        "",
        "## The 71 legacy intents",
        "",
        "They still name digests that exist nowhere, and this gate does not",
        "backfill them. The digests cannot be reconstructed: the snapshots they",
        "were built from are not guaranteed unchanged, and manufacturing one",
        "would produce a record that looks like evidence and is not.",
        "",
        "What changed is that no *new* intent has to be in that position. The",
        "linkage is measured on every call and can be enforced with",
        "`require_persisted_digest=True`.",
        "",
        "## What would make the enforcement unconditional",
        "",
        "```text",
        "1  every live intent resolves to a persisted digest",
        "2  the legacy rows are archived or accepted as pre-table history",
        "3  the flag default flips, in a change somebody reviews",
        "```",
        "",
        "Step 2 is a decision rather than work: those intents are not wrong,",
        "they are older than the table.",
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
        "Gate 152 — audit replay / evidence ledger. A persisted digest is the",
        "first thing a replay has to be able to read, which is why it came",
        "first.",
        "",
    ]
    return "\n".join(lines)


def build_digest_persistence_artifacts() -> dict[str, str]:
    """Every artifact body, by filename. Deterministic; reads no database."""
    files = {
        SURVEY_FILE: _json(_survey()),
        SCHEMA_FILE: _json(_schema_contract()),
        ROUNDTRIP_FILE: _json(_roundtrip()),
        ROUTE_FILE: _json(_route_smoke()),
        LINKAGE_FILE: _json(_linkage()),
        HASH_FILE: _json(_hash_stability()),
        READINESS_FILE: _json(_readiness()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_digest_persistence_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_digest_persistence_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def digest_persistence_artifact_invariant_failures(
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
