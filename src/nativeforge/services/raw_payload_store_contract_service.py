"""Raw payload store contract (Gate 93E).

Defines what must be stored before any collector may activate. It stores
nothing and fetches nothing — it validates a record's shape and reports what a
store must guarantee.

## Why this exists before the collectors do

Gates 87 through 89 spent four gates measuring the same wound from the other
end: 185 corpus records, of which only 18 carry independent transport evidence,
because when those records were made nobody kept the bytes. Every flag saying
``never_synthesized: True`` turned out to be a hardcoded literal, and the guard
checking it compared flags to flags.

The fix is not a better flag. It is keeping the payload, so a record's origin is
a thing you can re-derive rather than a thing you have to believe. Building 381
sources' worth of collectors before the store exists would reproduce the problem
at scale, which is why ``raw_payload_store`` is a required precondition for all
five Phase 1 sources.

## A parsed record is not evidence of collection

``parser_status`` is deliberately separate from the payload fields, and
``payload_is_trustworthy_as_collected`` requires the payload half — not the
parsed half. A parsed opportunity with no stored payload behind it is a claim,
not a collection.

## Secret scanning is a promotion gate

Gate 89 found a committed 143-character HS256 JWT sitting in a fixture, tracked
since 2026-06-20 and not gitignored. Raw API responses are exactly where the
next one arrives — a signed URL, a session token echoed in a header. So
``secret_scan_status`` must be affirmatively ``clean`` before a payload is
promoted to storage, and ``pending``/``unknown`` do not qualify.

Response headers are stored as a **hash**, never verbatim, because that is where
``Authorization`` and ``Set-Cookie`` live.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_raw_payload_store_contract_v1"

# Every field a stored payload record must carry. Order is reporting order.
REQUIRED_FIELDS: tuple[str, ...] = (
    "payload_id",
    "source_id",
    "retrieved_at",
    "retrieval_method",
    "request_fingerprint",
    "response_status",
    "response_headers_hash",
    "raw_payload_hash",
    "raw_payload_size_bytes",
    "canonical_url",
    "attribution_required",
    "terms_status",
    "parser_status",
    "retention_policy",
    "redaction_status",
    "secret_scan_status",
)

# The subset without which a record cannot be called evidence of a fetch. These
# are checked for presence AND plausibility, not just presence.
EVIDENCE_CRITICAL_FIELDS: tuple[str, ...] = (
    "payload_id",
    "source_id",
    "retrieved_at",
    "raw_payload_hash",
)

RETRIEVAL_METHODS = frozenset(
    {"bulk_extract", "public_api", "public_api_with_key", "feed", "html_get", "manual"}
)

PARSER_STATUSES = frozenset(
    {"not_parsed", "parsed_ok", "parsed_with_errors", "parse_failed"}
)

RETENTION_POLICIES = frozenset(
    {"retain_indefinite", "retain_7_days", "retain_90_days", "retain_1_year"}
)

REDACTION_STATUSES = frozenset({"not_required", "redacted", "pending", "unknown"})
REDACTION_SATISFYING = frozenset({"not_required", "redacted"})

SECRET_SCAN_STATUSES = frozenset({"clean", "findings", "pending", "unknown"})
# Affirmative: only `clean` permits promotion. `pending` is not a pass.
SECRET_SCAN_SATISFYING = frozenset({"clean"})

# SHA-256 hex.
HASH_HEX_LENGTH = 64


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    if len(text) != HASH_HEX_LENGTH:
        return False
    return all(c in "0123456789abcdef" for c in text.lower())


def build_store_contract() -> dict[str, Any]:
    """The contract itself: what a conforming store must guarantee."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_fields": list(REQUIRED_FIELDS),
            "evidence_critical_fields": list(EVIDENCE_CRITICAL_FIELDS),
            "guarantees": [
                "a raw payload is written before its parsed form is trusted",
                "raw_payload_hash is SHA-256 hex and is required",
                "retrieved_at is required and is not inferred from a filename",
                "source_id is required; an orphan payload is not evidence",
                "response headers are stored as a hash, never verbatim",
                "secret scan must read clean before storage promotion",
                "retention policy is explicit per payload, never a default",
                "attribution requirement travels with the payload",
            ],
            "vocabularies": {
                "retrieval_method": sorted(RETRIEVAL_METHODS),
                "parser_status": sorted(PARSER_STATUSES),
                "retention_policy": sorted(RETENTION_POLICIES),
                "redaction_status": sorted(REDACTION_STATUSES),
                "secret_scan_status": sorted(SECRET_SCAN_STATUSES),
            },
            # This contract is a description, not an implementation.
            "store_implemented": False,
            "payloads_stored": 0,
            "fetch_performed": False,
            "network_access_performed": False,
            "fabricated": False,
        }
    )


def validate_payload_record(record: Any) -> dict[str, Any]:
    """Would this record be accepted by a conforming store? Nothing is written."""
    rec = record if isinstance(record, dict) else {}

    missing = [f for f in REQUIRED_FIELDS if rec.get(f) in (None, "")]
    present = [f for f in REQUIRED_FIELDS if f not in missing]

    problems: list[str] = []

    # Evidence-critical fields get checked for plausibility, not just presence.
    if not _is_sha256_hex(rec.get("raw_payload_hash")):
        problems.append("raw_payload_hash_is_not_sha256_hex")
    if rec.get("response_headers_hash") not in (None, "") and not _is_sha256_hex(
        rec.get("response_headers_hash")
    ):
        problems.append("response_headers_hash_is_not_sha256_hex")

    size = rec.get("raw_payload_size_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        problems.append("raw_payload_size_bytes_is_not_a_non_negative_int")
    elif size == 0 and "raw_payload_hash" not in missing:
        # A zero-byte body with a hash is the HUD dead-shell shape.
        problems.append("zero_byte_payload_recorded_as_content")

    if rec.get("retrieval_method") not in RETRIEVAL_METHODS:
        problems.append("retrieval_method_out_of_vocabulary")
    if rec.get("parser_status") not in PARSER_STATUSES:
        problems.append("parser_status_out_of_vocabulary")
    if rec.get("retention_policy") not in RETENTION_POLICIES:
        problems.append("retention_policy_out_of_vocabulary")
    if rec.get("redaction_status") not in REDACTION_STATUSES:
        problems.append("redaction_status_out_of_vocabulary")
    if rec.get("secret_scan_status") not in SECRET_SCAN_STATUSES:
        problems.append("secret_scan_status_out_of_vocabulary")

    # Headers must never be stored verbatim.
    if isinstance(rec.get("response_headers"), (dict, list, str)):
        problems.append("response_headers_stored_verbatim")

    scan_ok = rec.get("secret_scan_status") in SECRET_SCAN_SATISFYING
    redaction_ok = rec.get("redaction_status") in REDACTION_SATISFYING

    evidence_missing = [f for f in EVIDENCE_CRITICAL_FIELDS if f in missing]
    evidence_complete = not evidence_missing and not any(
        p.startswith("raw_payload_hash") for p in problems
    )

    accepted = not missing and not problems and scan_ok and redaction_ok

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "payload_id": rec.get("payload_id"),
            "source_id": rec.get("source_id"),
            "accepted": accepted,
            "fields_present": present,
            "fields_missing": missing,
            "evidence_critical_missing": evidence_missing,
            "problems": problems,
            "secret_scan_clean": scan_ok,
            "redaction_satisfied": redaction_ok,
            "promotion_allowed": bool(accepted and scan_ok),
            # The parsed form is only trustworthy if the payload half holds.
            "payload_is_trustworthy_as_collected": evidence_complete,
            "parser_status": rec.get("parser_status"),
            # This validator does not write, and does not fetch.
            "record_stored": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def store_contract_invariant_failures(payload: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if payload.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if payload.get("fetch_performed") is not False:
        fails.append("store_contract_claimed_a_fetch")

    # Contract-shaped payloads.
    if "required_fields" in payload:
        if list(payload.get("required_fields") or []) != list(REQUIRED_FIELDS):
            fails.append("required_field_list_altered")
        if payload.get("store_implemented") is not False:
            fails.append("contract_claimed_the_store_is_implemented")
        if payload.get("payloads_stored"):
            fails.append("contract_reported_stored_payloads")
        if payload.get("network_access_performed") is not False:
            fails.append("contract_claimed_network_access")
        for field in EVIDENCE_CRITICAL_FIELDS:
            if field not in (payload.get("required_fields") or []):
                fails.append(f"evidence_critical_field_dropped:{field}")

    # Validation-shaped payloads.
    if "accepted" in payload:
        if payload.get("record_stored") is not False:
            fails.append("validator_claimed_a_write")
        if payload.get("accepted") and payload.get("fields_missing"):
            fails.append("record_accepted_with_missing_fields")
        if payload.get("accepted") and payload.get("problems"):
            fails.append("record_accepted_with_problems")
        # Promotion requires an affirmatively clean scan.
        if payload.get("promotion_allowed") and not payload.get("secret_scan_clean"):
            fails.append("promotion_allowed_without_a_clean_secret_scan")
        if payload.get("accepted") and not payload.get("redaction_satisfied"):
            fails.append("record_accepted_without_redaction_resolved")
        # A record missing evidence-critical fields is never trustworthy.
        if payload.get("evidence_critical_missing") and payload.get(
            "payload_is_trustworthy_as_collected"
        ):
            fails.append("payload_trusted_without_evidence_critical_fields")
        # A parsed record cannot outrank its own missing payload.
        if (
            payload.get("parser_status") == "parsed_ok"
            and not payload.get("payload_is_trustworthy_as_collected")
            and payload.get("accepted")
        ):
            fails.append("parsed_record_accepted_without_trustworthy_payload")

    return fails
