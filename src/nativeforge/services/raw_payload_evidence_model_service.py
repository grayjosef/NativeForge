"""Raw payload evidence model (Gate 95B).

Represents a raw source response as **evidence**, before any parsed opportunity
derived from it may be trusted as collected.

## The number this exists to fix

Gates 87 through 89 measured the same wound from three angles and arrived at:
**185 corpus records, 18 with independent transport evidence.** The other 167
were parsed and persisted while the bytes were discarded, so their origin can
only be believed, not re-derived. Every flag asserting otherwise turned out to
be a hardcoded literal.

The fix is not a better flag. It is keeping the response, hashing it, and
refusing to call the parsed form "collected" until the response is retrievable.

## Deterministic identity

``payload_id`` derives from ``source_id + request_fingerprint +
response_body_hash``. The same response fetched twice produces the same id, so
a re-fetch is recognisable as a re-fetch rather than becoming a second record.
A caller may supply an explicit id, and one is generated only when it does not.

## Statuses, and which of them permit anything

``secret_scan_status``  only ``clean`` permits promotion. ``pending`` is not a
                        pass - Gate 89 found a committed JWT precisely because
                        nothing was ever affirmatively checked.
``redaction_status``    ``completed`` or ``not_required``.
``parser_status``       ``parsed`` or ``not_started``. A parse failure does not
                        invalidate the evidence - the bytes are still the bytes -
                        but it does stop the record being promoted on the
                        strength of a parse that did not happen.
``promotion_status``    ``quarantine`` is where everything starts.

## Live and fixture are mutually exclusive

``created_from_live_fetch`` and ``created_from_fixture`` cannot both be true,
and an invariant enforces it. A record that claims both is claiming its own
provenance is unknown, which is exactly the ambiguity Gate 88 found in the
corpus: records whose "recorded" flag described the flag rather than the fetch.

Both may be false - that is a record whose provenance was never stated, and it
cannot be promoted either.

## What evidence is not

``payload evidence does not imply live coverage`` and ``does not imply
monitoring is active`` are fields on every record, both constant, both checked.
A store full of fixture payloads is a store full of fixture payloads.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_raw_payload_evidence_model_v1"

REDACTION_STATUSES = frozenset({"not_required", "pending", "completed", "failed"})
REDACTION_SATISFYING = frozenset({"not_required", "completed"})

SECRET_SCAN_STATUSES = frozenset({"pending", "clean", "findings_blocked", "failed"})
# Affirmative. `pending` is not a pass.
SECRET_SCAN_SATISFYING = frozenset({"clean"})

PARSER_STATUSES = frozenset(
    {
        "not_started",
        "parsed",
        "parse_failed",
        "parser_unavailable",
        "human_review_required",
    }
)
PARSER_SATISFYING = frozenset({"not_started", "parsed"})

PROMOTION_STATUSES = frozenset(
    {"quarantine", "evidence_ready", "rejected", "superseded"}
)
# The one status that means this payload may back a collected record.
PROMOTION_PERMITTING = frozenset({"evidence_ready"})

RETRIEVAL_METHODS = frozenset(
    {
        "bulk_extract",
        "public_api",
        "public_api_with_key",
        "feed",
        "html_get",
        "manual",
        "fixture",
    }
)

REQUEST_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})

RETENTION_POLICIES = frozenset(
    {"retain_indefinite", "retain_7_days", "retain_90_days", "retain_1_year"}
)

TERMS_BLOCKING = frozenset({"TERMS_REVIEW_REQUIRED", "UNKNOWN"})
TERMS_HUMAN_ONLY = frozenset({"HUMAN_REVIEW_ONLY"})
TERMS_NON_BLOCKING = frozenset({"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"})
ALL_TERMS_STATUSES = TERMS_BLOCKING | TERMS_HUMAN_ONLY | TERMS_NON_BLOCKING

# Fields without which a record is not evidence of anything.
REQUIRED_FIELDS: tuple[str, ...] = (
    "payload_id",
    "source_id",
    "source_name",
    "source_type",
    "collector_id",
    "retrieved_at",
    "retrieval_method",
    "request_method",
    "request_url",
    "request_fingerprint",
    "canonical_url",
    "response_status",
    "response_headers_hash",
    "response_body_hash",
    "response_body_size_bytes",
    "content_type",
    "raw_payload_ref",
    "redaction_status",
    "secret_scan_status",
    "terms_status",
    "attribution_required",
    "parser_status",
    "promotion_status",
    "retention_policy",
    "created_from_live_fetch",
    "created_from_fixture",
    "blocked_reasons",
)

# The four that make a record re-derivable rather than merely described.
EVIDENCE_CRITICAL_FIELDS: tuple[str, ...] = (
    "source_id",
    "retrieved_at",
    "response_body_hash",
    "raw_payload_ref",
)

HASH_HEX_LENGTH = 64


class RawPayloadEvidenceError(ValueError):
    """Raised when a record cannot be built as evidence at all."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    if len(text) != HASH_HEX_LENGTH:
        return False
    return all(c in "0123456789abcdef" for c in text.lower())


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    """Deny by default: outside the vocabulary becomes the blocking member."""
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_payload_id(
    *, source_id: Any, request_fingerprint: Any, response_body_hash: Any
) -> str:
    """Deterministic: the same response twice is the same payload."""
    parts = [
        str(source_id or ""),
        str(request_fingerprint or ""),
        str(response_body_hash or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_payload_evidence(
    *,
    source_id: Any,
    retrieved_at: Any,
    response_body_hash: Any,
    raw_payload_ref: Any,
    request_fingerprint: Any = None,
    payload_id: Any = None,
    source_name: Any = None,
    source_type: Any = None,
    collector_id: Any = None,
    retrieval_method: Any = None,
    request_method: Any = "GET",
    request_url: Any = None,
    canonical_url: Any = None,
    response_status: Any = None,
    response_headers_hash: Any = None,
    response_body_size_bytes: Any = None,
    content_type: Any = None,
    redaction_status: Any = None,
    secret_scan_status: Any = None,
    terms_status: Any = None,
    attribution_required: bool = False,
    parser_status: Any = None,
    retention_policy: Any = None,
    created_from_live_fetch: bool = False,
    created_from_fixture: bool = False,
) -> dict[str, Any]:
    """One raw response as an evidence record. Nothing is fetched or written."""
    if not str(source_id or "").strip():
        raise RawPayloadEvidenceError("source_id is required")
    if not str(retrieved_at or "").strip():
        raise RawPayloadEvidenceError("retrieved_at is required")
    if not _is_sha256_hex(response_body_hash):
        raise RawPayloadEvidenceError(
            "response_body_hash is required and must be SHA-256 hex"
        )
    if not str(raw_payload_ref or "").strip():
        raise RawPayloadEvidenceError("raw_payload_ref is required")
    if created_from_live_fetch and created_from_fixture:
        raise RawPayloadEvidenceError(
            "created_from_live_fetch and created_from_fixture cannot both be true"
        )

    fingerprint = str(request_fingerprint or "")
    resolved_id = str(payload_id).strip() if payload_id else build_payload_id(
        source_id=source_id,
        request_fingerprint=fingerprint,
        response_body_hash=response_body_hash,
    )

    redaction = _norm(redaction_status, REDACTION_STATUSES, fallback="pending")
    scan = _norm(secret_scan_status, SECRET_SCAN_STATUSES, fallback="pending")
    parser = _norm(parser_status, PARSER_STATUSES, fallback="not_started")
    terms = _norm(terms_status, ALL_TERMS_STATUSES, fallback="UNKNOWN")
    method = _norm(retrieval_method, RETRIEVAL_METHODS, fallback="manual")
    verb = _norm(
        str(request_method or "GET").upper(), REQUEST_METHODS, fallback="GET"
    )
    retention = _norm(
        retention_policy, RETENTION_POLICIES, fallback="retain_indefinite"
    )

    blocked: list[str] = []
    if scan not in SECRET_SCAN_SATISFYING:
        blocked.append(f"secret_scan_not_clean:{scan}")
    if redaction not in REDACTION_SATISFYING:
        blocked.append(f"redaction_not_resolved:{redaction}")
    if terms in TERMS_BLOCKING:
        blocked.append(f"terms_status_blocks:{terms}")
    if terms in TERMS_HUMAN_ONLY:
        blocked.append(f"terms_human_review_only:{terms}")
    if parser not in PARSER_SATISFYING:
        blocked.append(f"parser_status_blocks:{parser}")
    if not (created_from_live_fetch or created_from_fixture):
        blocked.append("provenance_unstated")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "payload_id": resolved_id,
            "source_id": str(source_id),
            "source_name": source_name,
            "source_type": source_type,
            "collector_id": collector_id,
            "retrieved_at": str(retrieved_at),
            "retrieval_method": method,
            "request_method": verb,
            "request_url": request_url,
            "request_fingerprint": fingerprint,
            "canonical_url": canonical_url,
            "response_status": response_status,
            "response_headers_hash": response_headers_hash,
            "response_body_hash": str(response_body_hash),
            "response_body_size_bytes": response_body_size_bytes,
            "content_type": content_type,
            "raw_payload_ref": str(raw_payload_ref),
            "redaction_status": redaction,
            "secret_scan_status": scan,
            "terms_status": terms,
            "attribution_required": bool(attribution_required),
            "parser_status": parser,
            # Everything starts in quarantine. Promotion is a separate decision
            # made by the promotion gate, never asserted at construction.
            "promotion_status": "quarantine",
            "retention_policy": retention,
            "created_from_live_fetch": bool(created_from_live_fetch),
            "created_from_fixture": bool(created_from_fixture),
            "blocked_reasons": sorted(set(blocked)),
            # Constants. A store of payloads is not coverage.
            "implies_live_coverage": False,
            "implies_monitoring_active": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def evidence_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if record.get("fetch_performed") is not False:
        fails.append("evidence_model_claimed_a_fetch")

    for constant in ("implies_live_coverage", "implies_monitoring_active"):
        if record.get(constant) is not False:
            fails.append(f"evidence_claimed:{constant}")

    for field in REQUIRED_FIELDS:
        if field not in record:
            fails.append(f"required_field_absent:{field}")

    for field in EVIDENCE_CRITICAL_FIELDS:
        if not str(record.get(field) or "").strip():
            fails.append(f"evidence_critical_field_empty:{field}")

    if not _is_sha256_hex(record.get("response_body_hash")):
        fails.append("response_body_hash_is_not_sha256_hex")
    if record.get("response_headers_hash") and not _is_sha256_hex(
        record.get("response_headers_hash")
    ):
        fails.append("response_headers_hash_is_not_sha256_hex")

    # Headers are hashed, never retained verbatim: that is where Authorization
    # and Set-Cookie live.
    if isinstance(record.get("response_headers"), (dict, list, str)):
        fails.append("response_headers_stored_verbatim")

    for field, vocabulary in (
        ("redaction_status", REDACTION_STATUSES),
        ("secret_scan_status", SECRET_SCAN_STATUSES),
        ("parser_status", PARSER_STATUSES),
        ("promotion_status", PROMOTION_STATUSES),
        ("retention_policy", RETENTION_POLICIES),
        ("retrieval_method", RETRIEVAL_METHODS),
        ("request_method", REQUEST_METHODS),
    ):
        if record.get(field) not in vocabulary:
            fails.append(f"{field}_out_of_vocabulary")

    if record.get("terms_status") not in ALL_TERMS_STATUSES:
        fails.append("terms_status_out_of_vocabulary")

    # Provenance is exclusive, and stating neither is not a third option that
    # permits anything.
    if record.get("created_from_live_fetch") and record.get("created_from_fixture"):
        fails.append("record_claims_both_live_and_fixture_provenance")

    # A quarantined record with no blockers, or a promoted one with blockers,
    # means the two disagree.
    if record.get("promotion_status") in PROMOTION_PERMITTING and record.get(
        "blocked_reasons"
    ):
        fails.append("evidence_ready_with_blocked_reasons")

    return fails


def summarise_evidence(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_promotion = {status: 0 for status in sorted(PROMOTION_STATUSES)}
    by_scan = {status: 0 for status in sorted(SECRET_SCAN_STATUSES)}
    for record in records:
        promotion = record.get("promotion_status")
        if promotion in by_promotion:
            by_promotion[promotion] += 1
        scan = record.get("secret_scan_status")
        if scan in by_scan:
            by_scan[scan] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(records),
            "by_promotion_status": by_promotion,
            "by_secret_scan_status": by_scan,
            "live_fetch_records": sum(
                1 for r in records if r.get("created_from_live_fetch")
            ),
            "fixture_records": sum(
                1 for r in records if r.get("created_from_fixture")
            ),
            "implies_live_coverage": False,
            "implies_monitoring_active": False,
            "fabricated": False,
        }
    )
