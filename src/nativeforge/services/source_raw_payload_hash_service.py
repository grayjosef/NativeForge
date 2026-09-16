"""Raw payload hashing (Gate 160E).

## This composes Gate 97C. It does not reimplement it.

`s3_raw_payload_body_store_service.body_hash` is already bytes-first sha256, and
it is the hash the production object key is derived from:

```text
raw_payloads/<hash[:2]>/<hash[2:4]>/<hash>.bin
```

If this module computed its own digest, the controlled-dev-demo row and the
production object key could disagree about which bytes they mean — which is
exactly the failure content addressing exists to prevent. So `body_hash` is
imported, and this module contains no `hashlib` call for payload bytes. A test
parses the AST to prove it.

## Bytes are hashed. Text is decoded separately.

```text
hash        sha256 of the EXACT stored bytes
encoding    recorded beside the hash, never applied before it
```

The rule that matters: **never hash a reserialized structure.** If a collector
receives 412 bytes of JSON, the evidence hash is of those 412 bytes — not of
`json.dumps(json.loads(body))`, which reorders keys, changes whitespace and
produces a digest that no longer identifies what arrived.

`json.dumps` round-tripping is what an artifact writer does for a report. It is
the wrong operation for evidence, and the two look identical in a diff.

## What a decode does and does not change

`describe_encoding` reports whether the bytes decode as UTF-8 and what they look
like. It returns the hash unchanged, because a decode is an interpretation of
bytes and interpretations do not alter evidence. A body that is not valid UTF-8
is still storable and still hashable; it is simply not text.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.s3_raw_payload_body_store_service import (
    HASH_HEX_LENGTH,
    body_hash,
)

SCHEMA_VERSION = "nf_source_raw_payload_hash_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

HASH_ALGORITHM = "sha256"

#: Named so a caller reports where the digest came from rather than assuming.
COMPOSED_FROM = "s3_raw_payload_body_store_service.body_hash"

#: A database row is not an object. Gate 141's object adapter accepts 16 MiB;
#: this is a controlled-dev-demo body living in a SQLite row, and Gate 96C's
#: own reasoning applies - "a 78 MB Grants.gov extract is not a database row".
#:
#: 1 MiB is large enough for a synthetic fixture or a realistic API page, and
#: small enough that nobody mistakes this for the production path.
MAX_PAYLOAD_BYTES = 1024 * 1024

TEXT_ENCODING = "utf-8"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def as_bytes(body: Any) -> bytes | None:
    """The exact bytes to hash and store.

    A `str` is encoded once, here, and that encoding is recorded. Everything
    else must already be bytes: accepting a dict would mean serializing it,
    and a serialized dict is not the response that arrived.
    """
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray | memoryview):
        return bytes(body)
    if isinstance(body, str):
        return body.encode(TEXT_ENCODING)
    return None


def describe_encoding(payload: bytes) -> dict[str, Any]:
    """How the bytes decode. Reported beside the hash, never applied before it."""
    try:
        text = payload.decode(TEXT_ENCODING)
    except (UnicodeDecodeError, AttributeError):
        return {
            "declared_encoding": TEXT_ENCODING,
            "decodes_as_utf8": False,
            "is_text": False,
            "character_count": None,
        }
    return {
        "declared_encoding": TEXT_ENCODING,
        "decodes_as_utf8": True,
        "is_text": True,
        "character_count": len(text),
    }


def hash_payload(
    *, body: Any, max_bytes: int = MAX_PAYLOAD_BYTES
) -> dict[str, Any]:
    """Hash the exact bytes, and say whether they may be stored.

    Oversize is a refusal, not a truncation. Truncating and then hashing would
    produce a digest of bytes that never existed anywhere.
    """
    payload = as_bytes(body)

    if payload is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "usable": False,
                "blocked_reasons": ["body_is_not_bytes_or_text"],
                "payload_sha256": None,
                "payload_size_bytes": None,
                "max_payload_bytes": int(max_bytes),
                "algorithm": HASH_ALGORITHM,
                "composed_from": COMPOSED_FROM,
            }
        )

    size = len(payload)
    blocked: list[str] = []
    if size > int(max_bytes):
        blocked.append(f"payload_exceeds_max_bytes:{size}>{int(max_bytes)}")

    digest = body_hash(payload)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Hashable and storable are different questions. An oversize body
            # still has a hash; it just may not be persisted here.
            "usable": not blocked,
            "blocked_reasons": sorted(blocked),
            "payload_sha256": digest,
            "payload_size_bytes": size,
            "max_payload_bytes": int(max_bytes),
            "within_size_limit": size <= int(max_bytes),
            "algorithm": HASH_ALGORITHM,
            "composed_from": COMPOSED_FROM,
            "hashed_exact_bytes": True,
            "reserialized_before_hashing": False,
            "encoding": describe_encoding(payload),
            "is_empty": size == 0,
        }
    )


def verify_payload(*, body: Any, expected_sha256: Any) -> dict[str, Any]:
    """Do these bytes still hash to what was recorded?

    Used on readback. A store that writes a hash and never checks it again has
    recorded an intention rather than verified a fact.
    """
    payload = as_bytes(body)
    expected = str(expected_sha256 or "").strip().lower()

    if payload is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "hash_verified": False,
                "blocked_reasons": ["body_is_not_bytes_or_text"],
                "expected_sha256": expected or None,
                "actual_sha256": None,
            }
        )

    actual = body_hash(payload)
    blocked: list[str] = []
    if len(expected) != HASH_HEX_LENGTH:
        blocked.append(f"expected_hash_is_not_a_sha256_hex_digest:{len(expected)}")
    if expected and actual != expected:
        # The single most important refusal in this gate: the stored bytes are
        # not the bytes that were recorded.
        blocked.append("stored_bytes_do_not_match_the_recorded_hash")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "hash_verified": not blocked,
            "blocked_reasons": sorted(blocked),
            "expected_sha256": expected or None,
            "actual_sha256": actual,
            "payload_size_bytes": len(payload),
            "algorithm": HASH_ALGORITHM,
            "composed_from": COMPOSED_FROM,
        }
    )


def hash_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a hash result that contradicts itself."""
    fails: list[str] = []

    digest = str(result.get("payload_sha256") or result.get("actual_sha256") or "")
    if digest and len(digest) != HASH_HEX_LENGTH:
        fails.append(f"digest_is_not_a_sha256_hex_digest:{len(digest)}")
    if digest and digest != digest.lower():
        fails.append("digest_is_not_lowercase_hex")

    if result.get("algorithm") not in (None, HASH_ALGORITHM):
        fails.append(f"unexpected_algorithm:{result.get('algorithm')}")

    if result.get("reserialized_before_hashing"):
        fails.append("the_body_was_reserialized_before_hashing")
    if "hashed_exact_bytes" in result and not result.get("hashed_exact_bytes"):
        fails.append("the_hash_does_not_cover_the_exact_bytes")

    # usable and blocked_reasons must agree, both directions.
    if result.get("usable") and result.get("blocked_reasons"):
        fails.append("usable_alongside_blocked_reasons")
    if "usable" in result and not result.get("usable") and not result.get(
        "blocked_reasons"
    ):
        fails.append("unusable_without_naming_a_reason")

    if result.get("hash_verified") and result.get("blocked_reasons"):
        fails.append("hash_verified_alongside_blocked_reasons")

    size = result.get("payload_size_bytes")
    limit = result.get("max_payload_bytes")
    if (
        isinstance(size, int)
        and isinstance(limit, int)
        and result.get("usable")
        and size > limit
    ):
        fails.append("an_oversize_payload_was_reported_usable")

    return sorted(set(fails))
