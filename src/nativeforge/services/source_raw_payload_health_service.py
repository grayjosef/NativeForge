"""Raw payload persistence health (Gate 160K).

## The lane, and the two things it must say at once

```text
raw_payload_persistence_ready = True    bytes land, verify and replay
object_store_configured       = False   and production storage is NOT ready
collectors_invoked            = 0
live_source_calls             = 0
source_monitoring_live        = False
```

A working landing zone is the most plausible thing in this gate to mistake for a
working collector. Bytes now persist, hash and replay; nothing has ever fetched
any of them, and every byte in the store was handed in by a caller.

## `object_store_configured` is measured, not declared

It comes from `s3_raw_payload_body_store_service.build_client_config`, which
reads the settings. Gate 97C built the production body store; nobody has given
it a bucket. Reporting `False` here is the same fact Gate 96E's readiness lane
already derives, read from the same place rather than restated.

A gate that wrote `object_store_configured: False` as a constant would be
correct today and wrong the day somebody configures one, without anything
changing in the code that says so.

## What ready does not mean

`raw_payload_persistence_ready` means the spine works in
`controlled_dev_demo`. It does not mean production raw payload storage is
available - that needs the object store, and
`production_raw_payload_store_available` stays False until it exists.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_raw_payload_repository import (
    MAX_PAYLOAD_BYTES,
    MODE_DATABASE,
    PAYLOAD_STATUSES,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_response_metadata_filter_service import (
    ALLOWED_RESPONSE_HEADERS,
    CREDENTIAL_HEADERS,
)

SCHEMA_VERSION = "nf_source_raw_payload_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

CONDITIONS: tuple[str, ...] = (
    "table_exists",
    "exact_bytes_round_trip",
    "write_hash_verified",
    "readback_hash_verified",
    "tamper_detected",
    "attempt_conflict_refused",
    "secret_headers_refused",
    "safe_headers_survive",
    "oversize_refused",
    "archived_still_readable",
    "nothing_was_fetched",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "table_exists": (
        "nf_source_collection_raw_payloads, created by migration 0046"
    ),
    "exact_bytes_round_trip": (
        "the bytes read back are byte-identical to the bytes written, "
        "including bodies that are not valid UTF-8"
    ),
    "write_hash_verified": (
        "the store re-hashed the bytes it was handed and compared them with "
        "the declared hash, rather than trusting the caller's arithmetic"
    ),
    "readback_hash_verified": (
        "the store re-hashed the bytes it read back. A store that records a "
        "hash and never checks it again has recorded an intention."
    ),
    "tamper_detected": (
        "a body changed underneath its row failed replay, and replay returned "
        "NO bytes rather than bytes with a warning beside them"
    ),
    "attempt_conflict_refused": (
        "the same attempt offering different bytes was refused and both "
        "hashes named. Overwriting would destroy the evidence that they "
        "disagreed."
    ),
    "secret_headers_refused": (
        "Authorization, Cookie, Set-Cookie and X-API-Key were refused by "
        "header-name membership, and a header nobody has classified was "
        "refused for not being on the allowlist"
    ),
    "safe_headers_survive": (
        "Content-Type, ETag and the rest of the allowlist were KEPT. A filter "
        "that refuses everything passes every refusal test and is useless - "
        "Gate 160 shipped exactly that for one commit, by calling the secret "
        "scanner with the wrong keyword."
    ),
    "oversize_refused": (
        "a body over the limit was refused deterministically rather than "
        "truncated. Truncating and then hashing produces a digest of bytes "
        "that never existed anywhere."
    ),
    "archived_still_readable": (
        "an archived payload replayed. Archive is a lifecycle state, not a "
        "deletion: nothing here has an approved retention policy, so nothing "
        "deletes."
    ),
    "nothing_was_fetched": (
        "zero collectors invoked and zero live source calls, and the database "
        "refuses a row claiming either"
    ),
}

#: Conditions a single request cannot honestly measure.
NOT_MEASURABLE_BY_A_REQUEST: tuple[str, ...] = ()

READY_DOES_NOT_MEAN: tuple[str, ...] = (
    "a source was contacted",
    "a collector ran",
    "these bytes came from anywhere",
    "production raw payload storage is available",
    "an object store is configured",
    "a job was completed",
    "monitoring is live",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def detect_object_store_configured() -> bool:
    """Measured from Gate 97C's own config, not declared here."""
    try:
        from nativeforge.services.s3_raw_payload_body_store_service import (
            build_client_config,
        )
    except ImportError:  # pragma: no cover - the store is part of the repo
        return False
    try:
        return bool(build_client_config().get("configured"))
    except Exception:  # noqa: BLE001
        return False


def build_raw_payload_health(
    *,
    table_exists: Any = None,
    write_result: dict[str, Any] | None = None,
    replay_result: dict[str, Any] | None = None,
    tamper_result: dict[str, Any] | None = None,
    conflict_result: dict[str, Any] | None = None,
    metadata_result: dict[str, Any] | None = None,
    oversize_result: dict[str, Any] | None = None,
    archived_replay_result: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
    bytes_round_tripped: Any = None,
) -> dict[str, Any]:
    """Report the lane from results somebody else measured.

    Opens no connection and persists nothing, so it cannot pass its own lane by
    doing the work it is grading.
    """
    write = write_result or {}
    replay = replay_result or {}
    tamper = tamper_result or {}
    conflict = conflict_result or {}
    metadata = metadata_result or {}
    oversize = oversize_result or {}
    archived = archived_replay_result or {}
    totals = counts or {}

    blockers: list[str] = []
    if totals:
        for failure in raw_payload_invariant_failures(totals):
            blockers.append(f"counts:{failure}")

    claiming_collector = int(totals.get("rows_claiming_a_collector") or 0)
    claiming_fetch = int(totals.get("rows_claiming_a_live_fetch") or 0)
    oversize_rows = int(totals.get("rows_over_the_size_limit") or 0)

    if claiming_collector:
        blockers.append(f"a_row_claims_a_collector:{claiming_collector}")
    if claiming_fetch:
        blockers.append(f"a_row_claims_a_live_fetch:{claiming_fetch}")
    if oversize_rows:
        blockers.append(f"a_row_exceeds_the_size_limit:{oversize_rows}")

    safe_kept = set(metadata.get("safe_headers") or {})
    refused = set(metadata.get("refused_header_names") or [])

    measured = {
        "table_exists": bool(table_exists),
        "exact_bytes_round_trip": bool(bytes_round_tripped),
        "write_hash_verified": bool(write.get("write_hash_verified")),
        "readback_hash_verified": bool(write.get("readback_hash_verified")),
        # Both halves: refused AND returned no body. Reporting a tamper while
        # handing the bytes over anyway would put the caller in the position
        # of noticing.
        "tamper_detected": bool(
            tamper
            and not tamper.get("hash_verified")
            and not tamper.get("replayable")
            and tamper.get("body_base64") is None
        ),
        "attempt_conflict_refused": bool(
            conflict
            and not conflict.get("persisted")
            and any(
                "already_stored_different_bytes" in reason
                for reason in (conflict.get("blocked_reasons") or [])
            )
        ),
        "secret_headers_refused": bool(
            metadata
            and {"authorization", "cookie", "set-cookie", "x-api-key"} & refused
            and not (safe_kept & CREDENTIAL_HEADERS)
        ),
        # The condition that catches a filter which refuses everything.
        "safe_headers_survive": bool(
            safe_kept and safe_kept <= ALLOWED_RESPONSE_HEADERS
        ),
        "oversize_refused": bool(
            oversize
            and not oversize.get("persisted")
            and any(
                "exceeds_max_bytes" in reason
                for reason in (oversize.get("blocked_reasons") or [])
            )
        ),
        "archived_still_readable": bool(
            archived and archived.get("archived") and archived.get("replayable")
        ),
        "nothing_was_fetched": bool(totals)
        and claiming_collector == 0
        and claiming_fetch == 0,
    }

    missing = sorted(name for name, ok in measured.items() if not ok)
    blockers.extend(f"condition_not_met:{name}" for name in missing)

    ready = all(measured.values()) and not blockers

    by_status = totals.get("by_status") or {}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "raw_payload_persistence_ready": ready,
            "conditions": measured,
            "conditions_expected": list(CONDITIONS),
            "condition_evidence": CONDITION_EVIDENCE,
            "conditions_not_met": missing,
            "blockers": sorted(set(blockers)),
            "blocker_count": len(set(blockers)),
            # ---- the store -------------------------------------------------
            "storage_mode": MODE_DATABASE,
            "max_payload_size_bytes": MAX_PAYLOAD_BYTES,
            "payloads_total": int(totals.get("total") or 0),
            "payloads_by_status": by_status,
            "payloads_archived": int(by_status.get("archived") or 0),
            "payloads_hash_verified": int(
                bool(write.get("readback_hash_verified"))
            )
            + int(bool(replay.get("hash_verified"))),
            "payload_statuses": sorted(PAYLOAD_STATUSES),
            "total_bytes_stored": int(totals.get("total_bytes") or 0),
            "distinct_payload_hashes": int(totals.get("distinct_hashes") or 0),
            "retention_by_policy": totals.get("by_retention_policy") or {},
            # ---- refusals, counted ----------------------------------------
            "tamper_failures": int(measured["tamper_detected"]),
            "secret_header_refusals": len(refused & CREDENTIAL_HEADERS),
            "unrecognised_header_refusals": len(refused - CREDENTIAL_HEADERS),
            "safe_headers_kept": sorted(safe_kept),
            "allowlist_size": len(ALLOWED_RESPONSE_HEADERS),
            # ---- production storage, measured rather than declared --------
            "object_store_configured": detect_object_store_configured(),
            "production_raw_payload_store_available": False,
            "why_production_is_not_available": (
                "Gate 97C's S3 body store is built and has no bucket, endpoint "
                "or credential. This lane is about the controlled_dev_demo "
                "spine, not production storage."
            ),
            # ---- the boundary ---------------------------------------------
            "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            "emails_sent": 0,
            "object_store_calls": 0,
            "approved_source_count": 0,
            "jobs_completed": 0,
            "creates_execution_proof": False,
            "source_monitoring_live": False,
        }
    )


def raw_payload_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims a fetch, or contradicts itself."""
    fails: list[str] = []

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "emails_sent",
        "object_store_calls",
        "approved_source_count",
        "jobs_completed",
    ):
        if int(health.get(counter) or 0) != 0:
            fails.append(f"health_counted:{counter}={health.get(counter)}")

    for claim in (
        "source_monitoring_live",
        "creates_execution_proof",
        "production_raw_payload_store_available",
    ):
        if health.get(claim):
            fails.append(f"health_claimed:{claim}")

    # The Gate 154 defect, both directions.
    if health.get("raw_payload_persistence_ready") and health.get("blockers"):
        fails.append("ready_alongside_blockers")
    if health.get("raw_payload_persistence_ready") and health.get(
        "conditions_not_met"
    ):
        fails.append("ready_alongside_unmet_conditions")
    if not health.get("raw_payload_persistence_ready") and not health.get(
        "blockers"
    ):
        fails.append("not_ready_without_naming_a_blocker")

    conditions = health.get("conditions") or {}
    expected = set(health.get("conditions_expected") or ())
    if expected and set(conditions) != expected:
        fails.append("conditions_do_not_match_the_declared_set")

    evidence = health.get("condition_evidence") or {}
    for name in conditions:
        if not str(evidence.get(name) or "").strip():
            fails.append(f"condition_without_evidence:{name}")

    # Nothing kept may be a credential header.
    kept = set(health.get("safe_headers_kept") or [])
    if kept & CREDENTIAL_HEADERS:
        fails.append(
            "health_reported_a_kept_credential_header:"
            f"{sorted(kept & CREDENTIAL_HEADERS)}"
        )
    if kept - ALLOWED_RESPONSE_HEADERS:
        fails.append("health_reported_a_kept_header_off_the_allowlist")

    # A ready lane must not report production availability or a live store.
    if health.get("raw_payload_persistence_ready"):
        if not health.get("ready_does_not_mean"):
            fails.append("ready_without_stating_what_ready_does_not_mean")
        if conditions.get("nothing_was_fetched") is not True:
            fails.append("ready_while_something_was_fetched")
        if conditions.get("safe_headers_survive") is not True:
            fails.append("ready_while_the_filter_kept_nothing")

    by_status = health.get("payloads_by_status") or {}
    if by_status and sum(by_status.values()) != int(
        health.get("payloads_total") or 0
    ):
        fails.append("payloads_by_status_does_not_account_for_the_total")

    size = health.get("max_payload_size_bytes")
    if size is not None and int(size) != MAX_PAYLOAD_BYTES:
        fails.append(f"reported_size_limit_disagrees_with_the_store:{size}")

    return sorted(set(fails))
