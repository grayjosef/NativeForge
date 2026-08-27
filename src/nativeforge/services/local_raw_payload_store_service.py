"""Deterministic local raw payload store (Gate 95C).

Local storage for tests, fixtures, and future collector dry-runs. It is **not**
a production store and this module never claims to be one.

## Refuses by default

``local_storage_enabled`` defaults to ``False`` and a write with it unset
raises. Not returns-a-sentinel: raises, following Gate 77B's reasoning that a
silent no-op is indistinguishable from a successful write, which is how a
fixture got overwritten with a placeholder.

``customer_data_allowed`` defaults to ``False`` as well, and is a separate
switch. A payload carrying customer data is refused unless the caller says so
explicitly - two different mistakes need two different opt-ins.

## Content-addressed

The body is stored at ``bodies/<hash[:2]>/<hash>.bin`` and the metadata at
``metadata/<payload_id>.json``. The same bytes stored twice land in the same
place, so a re-fetch does not duplicate storage and a corrupted file is
detectable by re-hashing its own path.

## retrieved_at comes from the caller

The store never calls ``now()``. A timestamp the store invents is a timestamp
about the store, not about the fetch - and it would make the same payload write
differently on every run, which is exactly what the determinism tests exist to
catch. The caller supplies it because the caller is the one that made the
request.

## Secrets never reach disk unredacted

Every write scans first. Findings block the write unless a redacted body is
supplied, and what is stored is the redacted body with the redacted hash. Gate
89 found a JWT committed inside a recorded API response; a store that writes
bodies without scanning them is a machine for repeating that.

## Not in git

``artifacts/`` is not gitignored in this repo and a dozen artifact directories
are committed deliberately, so the store root would be one ``git add`` away from
putting response bodies into history. Gate 95 adds an explicit ignore rule for
``artifacts/raw_payload_store/``. The readiness artifacts live in a *different*
directory precisely so that one can be committed and this one cannot.

## Nothing here fetches

There is no HTTP client, no transport, and no URL retrieval. The store takes
bytes the caller already has.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nativeforge.services.raw_payload_evidence_model_service import (
    RawPayloadEvidenceError,
    build_payload_evidence,
)
from nativeforge.services.raw_payload_secret_scan_service import (
    scan_payload_for_secrets,
)

SCHEMA_VERSION = "nf_local_raw_payload_store_v1"

STORE_ROOT = "artifacts/raw_payload_store"
BODIES_DIR = "bodies"
METADATA_DIR = "metadata"

# Bridged from customer_data_policy_service rather than redeclared. This store
# operates at exactly one of those modes and cannot reach the others.
STORAGE_MODE = "local_dev_only"
PRODUCTION_STORAGE_MODE = "production_object_storage"

WRITE_STATUSES = frozenset({"written", "refused", "deduplicated"})


class LocalPayloadStoreError(RuntimeError):
    """Raised when a write is refused. Names the reason."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def body_hash(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def headers_hash(headers: dict[str, Any] | None) -> str:
    """Headers are hashed, never stored. Authorization lives in headers."""
    canonical = json.dumps(
        {str(k).lower(): str(v) for k, v in sorted((headers or {}).items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def body_path_for(digest: str) -> str:
    """Content-addressed: same bytes, same path."""
    return f"{BODIES_DIR}/{digest[:2]}/{digest}.bin"


def metadata_path_for(payload_id: str) -> str:
    return f"{METADATA_DIR}/{payload_id}.json"


def store_raw_payload(
    *,
    source_id: Any,
    retrieved_at: Any,
    body: Any,
    request_fingerprint: Any = None,
    headers: dict[str, Any] | None = None,
    local_storage_enabled: bool = False,
    customer_data_allowed: bool = False,
    contains_customer_data: bool = False,
    created_from_fixture: bool = False,
    created_from_live_fetch: bool = False,
    activation_preflight: dict[str, Any] | None = None,
    redacted_body: Any = None,
    store_root: Any = None,
    repo_root: Any = None,
    **evidence_fields: Any,
) -> dict[str, Any]:
    """Write one payload locally. Refuses unless explicitly enabled."""
    if local_storage_enabled is not True:
        raise LocalPayloadStoreError(
            "local payload storage is disabled. "
            f"caller must pass local_storage_enabled=True. source_id={source_id!r}"
        )

    if contains_customer_data and customer_data_allowed is not True:
        raise LocalPayloadStoreError(
            "payload is marked as containing customer data and "
            "customer_data_allowed is not True. refusing to write."
        )

    if created_from_live_fetch and created_from_fixture:
        raise RawPayloadEvidenceError(
            "created_from_live_fetch and created_from_fixture cannot both be true"
        )

    # A live-fetch payload may only be stored behind a passed preflight. A
    # fixture never contacted a source, so there is no activation to require.
    if created_from_live_fetch:
        if activation_preflight is None:
            raise LocalPayloadStoreError(
                "live-fetch payload requires an activation preflight; none supplied"
            )
        if not activation_preflight.get("activation_allowed"):
            raise LocalPayloadStoreError(
                "live-fetch payload refused: activation preflight did not pass "
                f"({activation_preflight.get('activation_status', 'unknown')})"
            )

    original = str(body or "")
    scan = scan_payload_for_secrets(body=original, headers=headers)

    if not scan["clean"]:
        if redacted_body is None:
            raise LocalPayloadStoreError(
                "payload contains "
                f"{scan['finding_count']} secret finding(s) "
                f"({', '.join(sorted({f['kind'] for f in scan['findings']}))}) "
                "and no redacted body was supplied. refusing to write."
            )
        stored_body = str(redacted_body)
        rescan = scan_payload_for_secrets(body=stored_body, headers=None)
        if not rescan["clean"]:
            raise LocalPayloadStoreError(
                "redacted body still contains "
                f"{rescan['finding_count']} secret finding(s). refusing to write."
            )
        redaction_status = "completed"
        scan_status = "clean"
    else:
        stored_body = original
        redaction_status = "not_required"
        scan_status = "clean"

    digest = body_hash(stored_body)
    fingerprint = str(request_fingerprint or "")

    evidence = build_payload_evidence(
        source_id=source_id,
        retrieved_at=retrieved_at,
        response_body_hash=digest,
        raw_payload_ref=body_path_for(digest),
        request_fingerprint=fingerprint,
        response_headers_hash=headers_hash(headers) if headers else None,
        response_body_size_bytes=len(stored_body.encode("utf-8")),
        redaction_status=redaction_status,
        secret_scan_status=scan_status,
        created_from_fixture=created_from_fixture,
        created_from_live_fetch=created_from_live_fetch,
        **evidence_fields,
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / (str(store_root) if store_root else STORE_ROOT)

    body_file = out_dir / body_path_for(digest)
    metadata_file = out_dir / metadata_path_for(evidence["payload_id"])

    already = body_file.exists()
    body_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    body_file.write_text(stored_body, encoding="utf-8")
    metadata_file.write_text(
        json.dumps(
            {
                **evidence,
                "storage_mode": STORAGE_MODE,
                "local_raw_payload_store_available": True,
                "production_raw_payload_store_available": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "write_status": "deduplicated" if already else "written",
            "payload_id": evidence["payload_id"],
            "source_id": evidence["source_id"],
            "body_ref": body_path_for(digest),
            "metadata_ref": metadata_path_for(evidence["payload_id"]),
            "response_body_hash": digest,
            "redaction_status": redaction_status,
            "secret_scan_status": scan_status,
            "secret_findings": scan["finding_count"],
            "evidence": evidence,
            "storage_mode": STORAGE_MODE,
            # The two facts this store must never blur.
            "local_raw_payload_store_available": True,
            "production_raw_payload_store_available": False,
            "customer_data_stored": bool(contains_customer_data),
            "fetch_performed": False,
            "retrieved_at_generated_by_store": False,
            "fabricated": False,
        }
    )


def read_raw_payload(
    *,
    body_ref: str,
    store_root: Any = None,
    repo_root: Any = None,
) -> str | None:
    """Read a stored body back. Returns None when absent."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    path = root / (str(store_root) if store_root else STORE_ROOT) / body_ref
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def verify_stored_payload(
    *,
    body_ref: str,
    expected_hash: str,
    store_root: Any = None,
    repo_root: Any = None,
) -> dict[str, Any]:
    """Re-derive the hash from the stored bytes. This is the whole point."""
    stored = read_raw_payload(
        body_ref=body_ref, store_root=store_root, repo_root=repo_root
    )
    if stored is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "present": False,
                "hash_matches": False,
                "reason": "payload_absent",
                "fabricated": False,
            }
        )
    actual = body_hash(stored)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "present": True,
            "hash_matches": actual == expected_hash,
            "expected_hash": expected_hash,
            "actual_hash": actual,
            "reason": None if actual == expected_hash else "hash_mismatch",
            "fabricated": False,
        }
    )


def store_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    if "write_status" in result:
        if result.get("write_status") not in WRITE_STATUSES:
            fails.append("write_status_out_of_vocabulary")
        if result.get("fetch_performed") is not False:
            fails.append("store_claimed_a_fetch")
        if result.get("retrieved_at_generated_by_store") is not False:
            fails.append("store_generated_its_own_retrieved_at")
        if result.get("storage_mode") != STORAGE_MODE:
            fails.append("store_claimed_a_storage_mode_it_does_not_have")
        if result.get("production_raw_payload_store_available") is not False:
            fails.append("local_store_claimed_production_availability")
        if result.get("secret_scan_status") != "clean":
            fails.append("payload_written_without_a_clean_scan")
        # A content-addressed ref must contain its own hash.
        digest = str(result.get("response_body_hash") or "")
        if digest and digest not in str(result.get("body_ref") or ""):
            fails.append("body_ref_is_not_content_addressed")

    return fails
