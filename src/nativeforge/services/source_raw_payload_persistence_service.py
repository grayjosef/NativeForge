"""The raw payload write envelope (Gate 160G).

One door, six steps, in this order:

```text
1  validate the attempt identity        Gate 160B
2  filter the response metadata         Gate 160F, allowlist by header name
3  hash the EXACT bytes                 Gate 160E, composing Gate 97C
4  persist                              Gate 160D
5  re-read through the store
6  verify the readback hash
```

Step 6 is the one that makes this an envelope rather than a wrapper. A write
path that persists and returns is reporting an intention; a write path that
reads back and re-hashes is reporting a fact, and the difference is exactly the
tamper case this spine exists to catch.

## The bytes are supplied. Nothing here fetches.

`persist_raw_payload` takes a body from its caller. It opens no socket, imports
no HTTP client and has no URL parameter - only a `source_url_fingerprint`,
because URLs carry credentials in query strings often enough that storing one
would be a credential-storage decision nobody made.

Gate 160's verifier and tests pass **synthetic** payloads. When Gate 161 builds
a collector, it will hand its response bytes to this same door, and the door
will not be able to tell the difference - which is the point of proving the
landing zone before anything lands in it.

## A stored payload is not a fetched payload

The row records that bytes were persisted. It does not record that a source was
contacted, and `collector_invoked` / `live_fetch_performed` are columns the
database refuses to set true. This gate creates no execution proof, so Gate
158's `completed` stays unreachable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.repositories.source_collection_raw_payload_repository import (
    MODE_DATABASE,
    RETENTION_UNKNOWN,
    get_payload,
    persist_payload,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_collection_attempt_identity_service import (
    attempt_identity_invariant_failures,
    build_attempt_identity,
)
from nativeforge.services.source_raw_payload_hash_service import (
    MAX_PAYLOAD_BYTES,
    hash_invariant_failures,
    hash_payload,
)
from nativeforge.services.source_response_metadata_filter_service import (
    filter_response_metadata,
    metadata_filter_invariant_failures,
)

SCHEMA_VERSION = "nf_source_raw_payload_persistence_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Named so a caller reports the composition rather than inferring it.
COMPOSES = (
    "source_collection_attempt_identity_service.build_attempt_identity",
    "source_response_metadata_filter_service.filter_response_metadata",
    "source_raw_payload_hash_service.hash_payload",
    "source_collection_raw_payload_repository.persist_payload",
    "source_collection_raw_payload_repository.get_payload",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def fingerprint_url(url: Any) -> str | None:
    """A sha256 of the URL, never the URL.

    Query strings carry api keys. A fingerprint answers "is this the same
    endpoint as last time" without storing what the endpoint was, which is the
    only question the spine needs and the only one it can answer safely.
    """
    text = str(url or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _envelope(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "persisted": False,
        "deduplicated": False,
        "attempt_id": None,
        "payload_sha256": None,
        "payload_size_bytes": None,
        "write_hash_verified": False,
        "readback_hash_verified": False,
        "blocked_reasons": [],
        "invariant_failures": [],
        "composes": list(COMPOSES),
        # Constants. This door persists bytes it was handed.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "object_store_calls": 0,
        "object_store_configured": False,
        "emails_sent": 0,
        "storage_mode": MODE_DATABASE,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "body_was_supplied_not_fetched": True,
        "is_execution_proof": False,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    base["invariant_failures"] = sorted(set(base["invariant_failures"] or []))
    return _json_safe(base)


def persist_raw_payload(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    source_id: Any = None,
    attempt_number: Any = 1,
    collector_version: Any = None,
    body: Any = None,
    response_headers: Any = None,
    response_status: Any = None,
    source_url: Any = None,
    received_at: Any = None,
    retention_policy: str = RETENTION_UNKNOWN,
    fact_status: str = "synthetic_fixture",
    is_demo: bool = True,
    max_bytes: int = MAX_PAYLOAD_BYTES,
    # Gate 163: forwarded to the repository, where migration 0050's
    # CHECK requires a warrant for any row claiming a live fetch.
    collector_invoked: bool = False,
    live_fetch_performed: bool = False,
    authorized_source_id: Any = None,
) -> dict[str, Any]:
    """Persist one attempt's bytes through every check, and prove the readback.

    `source_url` is fingerprinted and discarded. There is no parameter that
    causes a fetch.
    """
    failures: list[str] = []

    # ---- 1. identity ------------------------------------------------------
    identity_kwargs: dict[str, Any] = {
        "job_id": job_id,
        "source_id": source_id,
        "attempt_number": attempt_number,
    }
    if collector_version is not None:
        identity_kwargs["collector_version"] = collector_version
    identity = build_attempt_identity(**identity_kwargs)
    failures.extend(attempt_identity_invariant_failures(identity))

    if not identity["usable"]:
        return _envelope(
            blocked_reasons=identity["blocked_reasons"],
            invariant_failures=failures,
            identity=identity,
        )

    # ---- 2. metadata ------------------------------------------------------
    metadata = filter_response_metadata(headers=response_headers)
    failures.extend(metadata_filter_invariant_failures(metadata))

    # ---- 3. hash the exact bytes -----------------------------------------
    hashed = hash_payload(body=body, max_bytes=max_bytes)
    failures.extend(hash_invariant_failures(hashed))

    blocked = list(metadata["blocked_reasons"]) + list(hashed["blocked_reasons"])
    if blocked:
        return _envelope(
            attempt_id=identity["attempt_id"],
            payload_sha256=hashed.get("payload_sha256"),
            payload_size_bytes=hashed.get("payload_size_bytes"),
            blocked_reasons=blocked,
            invariant_failures=failures,
            identity=identity,
            metadata=metadata,
            hash=hashed,
        )

    # ---- 4. persist -------------------------------------------------------
    written = persist_payload(
        connection=connection,
        organization_id=organization_id,
        attempt_id=identity["attempt_id"],
        attempt_number=identity["attempt_number"],
        collector_version=identity["collector_version"],
        job_id=identity["job_id"],
        source_id=identity["source_id"],
        body=body,
        # The hash the store must agree with. It re-hashes independently, so
        # this is a cross-check and not a shortcut.
        declared_sha256=hashed["payload_sha256"],
        received_at=received_at,
        response_status=response_status,
        media_type=metadata["safe_headers"].get("content-type"),
        encoding=hashed["encoding"]["declared_encoding"],
        source_url_fingerprint=fingerprint_url(source_url),
        safe_response_metadata=metadata["safe_headers"],
        retention_policy=retention_policy,
        fact_status=fact_status,
        collector_invoked=collector_invoked,
        live_fetch_performed=live_fetch_performed,
        authorized_source_id=authorized_source_id,
        is_demo=is_demo,
        max_bytes=max_bytes,
    )
    failures.extend(raw_payload_invariant_failures(written))

    if not (written["stored"] or written["deduplicated"]):
        return _envelope(
            attempt_id=identity["attempt_id"],
            payload_sha256=hashed["payload_sha256"],
            payload_size_bytes=hashed["payload_size_bytes"],
            blocked_reasons=written["blocked_reasons"],
            invariant_failures=failures,
            identity=identity,
            metadata=metadata,
            hash=hashed,
        )

    # ---- 5 and 6. re-read, and verify the hash again ---------------------
    #
    # Through the store's own reader, not by reaching into the row. A write
    # path that verifies its own copy of the bytes has verified nothing about
    # what was persisted.
    reread = get_payload(
        connection=connection,
        organization_id=organization_id,
        attempt_id=identity["attempt_id"],
        include_body=True,
    )
    failures.extend(raw_payload_invariant_failures(reread))

    return _envelope(
        attempt_id=identity["attempt_id"],
        persisted=bool(written["stored"]),
        deduplicated=bool(written["deduplicated"]),
        payload_sha256=hashed["payload_sha256"],
        payload_size_bytes=hashed["payload_size_bytes"],
        write_hash_verified=bool(written["hash_verified"]),
        readback_hash_verified=bool(reread["hash_verified"]),
        readback_sha256=reread.get("readback_sha256"),
        blocked_reasons=reread["blocked_reasons"],
        invariant_failures=failures,
        identity=identity,
        metadata=metadata,
        hash=hashed,
        payload=reread.get("payload"),
        safe_headers_kept=metadata["safe_header_count"],
        headers_refused=metadata["headers_refused"],
        refused_header_names=metadata["refused_header_names"],
    )


def persistence_invariant_failures(envelope: dict[str, Any]) -> list[str]:
    """Refuse an envelope that claims a fetch, or a write it did not verify."""
    fails: list[str] = list(envelope.get("invariant_failures") or [])

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "object_store_calls",
        "emails_sent",
    ):
        if int(envelope.get(counter) or 0) != 0:
            fails.append(f"envelope_counted:{counter}={envelope.get(counter)}")

    for claim in (
        "object_store_configured",
        "is_execution_proof",
        "source_monitoring_live",
    ):
        if envelope.get(claim):
            fails.append(f"envelope_claimed:{claim}")

    if not envelope.get("body_was_supplied_not_fetched"):
        fails.append("envelope_claimed_the_body_was_fetched")

    # A persisted payload must have been verified on both sides. A write that
    # reports success without a readback has reported an intention.
    if envelope.get("persisted"):
        if not envelope.get("write_hash_verified"):
            fails.append("persisted_without_a_verified_write_hash")
        if not envelope.get("readback_hash_verified"):
            fails.append("persisted_without_a_verified_readback_hash")
        if envelope.get("blocked_reasons"):
            fails.append("persisted_alongside_blocked_reasons")

    if envelope.get("persisted") and envelope.get("deduplicated"):
        fails.append("persisted_and_deduplicated_at_once")

    # Nothing may be stored above the limit.
    size = envelope.get("payload_size_bytes")
    limit = envelope.get("max_payload_bytes")
    if (
        isinstance(size, int)
        and isinstance(limit, int)
        and size > limit
        and (envelope.get("persisted") or envelope.get("deduplicated"))
    ):
        fails.append(f"an_oversize_payload_was_persisted:{size}>{limit}")

    # The metadata that reached the row must be what the filter permitted.
    metadata = envelope.get("metadata") or {}
    payload = envelope.get("payload") or {}
    if metadata and payload:
        kept = set(metadata.get("safe_headers") or {})
        stored = set(payload.get("response_header_metadata") or {})
        if stored - kept:
            fails.append(f"the_row_carries_headers_the_filter_refused:{stored - kept}")

    return sorted(set(fails))
