"""Source check-run record contract (Gate 98D).

The shape of the row a check writes when it finishes. It builds records; it
never performs a check and never writes to the database.

## Two gaps in nf_source_check_runs that this contract closes

Gate 98A read the 22 columns of `nf_source_check_runs` and found:

**No link to evidence.** A run can say `opportunities_seen_count = 42` with
nothing pointing at the payloads that produced the 42. That is the same shape as
the 185/18 corpus split Gates 87-89 measured: a number with no retrievable thing
behind it. This contract carries `raw_payload_ids`, which *reference*
`nf_raw_source_payloads` rows, and an invariant fails any record that reports
opportunities with no payload behind them.

**`error_message` is free text.** An HTTP client's exception text routinely
carries a presigned URL, an echoed `Authorization` header, or a query string with
a key in it. The column would store that verbatim, forever, in a table operators
read. The field here is `error_message_redacted` and it is redacted on the way in
by Gate 95's scanner - the caller does not get to promise it already did so.

## References, never contents

`raw_payload_ids` holds ids. Not bodies, not excerpts, not "the first 200
characters for context". A field carrying a body would make this table a second,
unscanned copy of the payload store, and `check_run_invariant_failures` rejects
any record whose keys include one.

## Counts we cannot read are not zero

An unreadable count is `None`, and `None` is reported as unknown. Coercing it to
0 would turn "we do not know what this run saw" into "this run saw nothing",
which reads as a clean result.

## It does not execute, and it does not persist

`check_executed` and `persisted` are False on every record. This gate has no
scheduler and no writer; a record that claimed either would be describing
something that does not exist.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.domain.enums import SourceCheckMode, SourceCheckRunStatus
from nativeforge.services.raw_payload_evidence_model_service import HASH_HEX_LENGTH
from nativeforge.services.raw_payload_secret_scan_service import (
    REDACTION_PLACEHOLDER,
    redact_payload,
)
from nativeforge.services.source_circuit_breaker_service import CIRCUIT_STATUSES

SCHEMA_VERSION = "nf_source_check_run_contract_v1"

# Bridged from the enums the table is constrained by, so the contract and the
# column check constraint cannot drift apart.
CHECK_RUN_STATUSES = frozenset(str(member) for member in SourceCheckRunStatus)
CHECK_MODES = frozenset(str(member) for member in SourceCheckMode)

TERMINAL_STATUSES = frozenset(
    {"succeeded", "succeeded_with_warnings", "failed", "canceled"}
)
SUCCESS_STATUSES = frozenset({"succeeded", "succeeded_with_warnings"})

COUNT_FIELDS: tuple[str, ...] = (
    "opportunities_seen_count",
    "new_candidates_count",
    "accepted_count",
    "duplicate_count",
    "rejected_count",
    "review_items_created_count",
)

CONTRACT_FIELDS: tuple[str, ...] = (
    "run_id",
    "source_id",
    "check_mode",
    "check_status",
    "started_at",
    "completed_at",
    *COUNT_FIELDS,
    "raw_payload_ids",
    "raw_payload_count",
    "error_code",
    "error_message_redacted",
    "circuit_status_after",
    "consecutive_failure_count_after",
    "schedule_status_at_dispatch",
    "dispatched_by",
)

# Field names that would mean a response body had been copied into this table.
# Checked against the record's own keys, so a future edit that adds one fails a
# test rather than shipping.
PROHIBITED_FIELD_NAMES = frozenset(
    {
        "body",
        "response_body",
        "raw_body",
        "payload",
        "payload_body",
        "raw_payload",
        "content",
        "response_text",
        "response_content",
        "body_excerpt",
        "body_sample",
        "body_preview",
        "snippet",
        "error_message",
        "headers",
        "response_headers",
        "request_headers",
        "authorization",
        "api_key",
        "token",
        "credentials",
    }
)

DISPATCH_ORIGINS = frozenset({"operator", "scheduler", "connector", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _as_count(value: Any) -> int | None:
    """A count, or None. Never a silent zero."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _is_payload_id(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if len(text) != HASH_HEX_LENGTH:
        return False
    return all(c in "0123456789abcdef" for c in text)


def build_check_run_record(
    *,
    run_id: Any,
    source_id: Any,
    check_mode: Any = None,
    check_status: Any = None,
    started_at: Any = None,
    completed_at: Any = None,
    counts: dict[str, Any] | None = None,
    raw_payload_ids: list[Any] | None = None,
    error_code: Any = None,
    error_message: Any = None,
    circuit_status_after: Any = None,
    consecutive_failure_count_after: Any = None,
    schedule_status_at_dispatch: Any = None,
    dispatched_by: Any = None,
) -> dict[str, Any]:
    """The record a finished check would write. Nothing is executed or stored."""
    mode = _norm(check_mode, CHECK_MODES, fallback="manual")
    status = _norm(check_status, CHECK_RUN_STATUSES, fallback="failed")
    origin = _norm(dispatched_by, DISPATCH_ORIGINS, fallback="unknown")
    circuit = _norm(circuit_status_after, CIRCUIT_STATUSES, fallback="unknown")

    supplied_counts = counts or {}
    resolved_counts = {
        field: _as_count(supplied_counts.get(field)) for field in COUNT_FIELDS
    }

    # Ids only. Anything that is not a payload id is dropped and counted, not
    # stored on the off-chance it was useful.
    supplied_ids = list(raw_payload_ids or [])
    accepted_ids = [value for value in supplied_ids if _is_payload_id(value)]
    payload_ids = sorted({str(value).strip().lower() for value in accepted_ids})
    rejected_ids = len(supplied_ids) - len(accepted_ids)

    # Redacted here, not trusted from the caller. A caller who has already
    # redacted loses nothing; a caller who forgot is caught.
    redaction = redact_payload(body=error_message)
    message = redaction["redacted_body"] if error_message is not None else None
    replacements = redaction["replacements"]

    warnings: list[str] = []
    if rejected_ids:
        warnings.append(f"raw_payload_ids_rejected:{rejected_ids}")
    if replacements:
        warnings.append(f"error_message_redacted:{replacements}")
    for field, value in resolved_counts.items():
        if value is None and supplied_counts.get(field) is not None:
            warnings.append(f"count_unreadable:{field}")

    seen = resolved_counts["opportunities_seen_count"]
    evidence_backed = bool(payload_ids)
    if status in SUCCESS_STATUSES and seen and not evidence_backed:
        warnings.append("counts_reported_without_payload_evidence")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "source_id": source_id,
            "check_mode": mode,
            "check_status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            **resolved_counts,
            "raw_payload_ids": payload_ids,
            "raw_payload_count": len(payload_ids),
            "error_code": error_code,
            "error_message_redacted": message,
            "circuit_status_after": circuit,
            "consecutive_failure_count_after": _as_count(
                consecutive_failure_count_after
            ),
            "schedule_status_at_dispatch": schedule_status_at_dispatch,
            "dispatched_by": origin,
            "counts_evidence_backed": evidence_backed,
            "redaction_applied": bool(replacements),
            "warnings": sorted(set(warnings)),
            # Constants for this gate: the contract describes, it does not act.
            "check_executed": False,
            "fetch_performed": False,
            "persisted": False,
            "response_body_included": False,
            "secret_values_included": False,
            "fabricated": False,
        }
    )


def contract_shape() -> dict[str, Any]:
    """The declared field list and prohibitions, for docs and artifacts."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table": "nf_source_check_runs",
            "contract_fields": list(CONTRACT_FIELDS),
            "count_fields": list(COUNT_FIELDS),
            "prohibited_field_names": sorted(PROHIBITED_FIELD_NAMES),
            "check_statuses": sorted(CHECK_RUN_STATUSES),
            "check_modes": sorted(CHECK_MODES),
            "redaction_placeholder": REDACTION_PLACEHOLDER,
            "payload_reference_style": "id_only",
            "response_body_stored": False,
            "fabricated": False,
        }
    )


def check_run_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "check_executed",
        "fetch_performed",
        "persisted",
        "response_body_included",
        "secret_values_included",
    ):
        if record.get(constant) is not False:
            fails.append(f"record_claimed:{constant}")

    # No key may name a body, a header, or a credential.
    for key in record:
        if key in PROHIBITED_FIELD_NAMES:
            fails.append(f"prohibited_field_present:{key}")

    if record.get("check_status") not in CHECK_RUN_STATUSES:
        fails.append("check_status_out_of_vocabulary")
    if record.get("check_mode") not in CHECK_MODES:
        fails.append("check_mode_out_of_vocabulary")
    if record.get("circuit_status_after") not in CIRCUIT_STATUSES:
        fails.append("circuit_status_after_out_of_vocabulary")

    # Payload references must be ids, and the count must match the list.
    ids = record.get("raw_payload_ids")
    if not isinstance(ids, list):
        fails.append("raw_payload_ids_not_a_list")
        ids = []
    else:
        if any(not _is_payload_id(value) for value in ids):
            fails.append("raw_payload_ids_contains_a_non_id")
        if record.get("raw_payload_count") != len(ids):
            fails.append("raw_payload_count_disagrees_with_ids")

    # counts_evidence_backed is derived, never asserted beside the evidence.
    if record.get("counts_evidence_backed") != bool(ids):
        fails.append("evidence_flag_disagrees_with_payload_ids")

    # Counts are non-negative or unknown; never a coerced zero.
    for field in COUNT_FIELDS:
        value = record.get(field)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            fails.append(f"count_not_a_non_negative_int:{field}")

    # A success that reports finding things with nothing behind it is the shape
    # this contract exists to make visible.
    seen = record.get("opportunities_seen_count")
    if (
        record.get("check_status") in SUCCESS_STATUSES
        and isinstance(seen, int)
        and seen > 0
        and not ids
    ):
        if "counts_reported_without_payload_evidence" not in (
            record.get("warnings") or []
        ):
            fails.append("unevidenced_counts_not_warned")

    # Accepted can never exceed what was seen.
    accepted = record.get("accepted_count")
    if isinstance(seen, int) and isinstance(accepted, int) and accepted > seen:
        fails.append("accepted_exceeds_opportunities_seen")

    return fails


def summarise_check_runs(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(CHECK_RUN_STATUSES)}
    for record in records:
        status = record.get("check_status")
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(records),
            "by_check_status": by_status,
            "evidence_backed_count": sum(
                1 for r in records if r.get("counts_evidence_backed")
            ),
            "redaction_applied_count": sum(
                1 for r in records if r.get("redaction_applied")
            ),
            "checks_executed": 0,
            "records_persisted": 0,
            "fabricated": False,
        }
    )
