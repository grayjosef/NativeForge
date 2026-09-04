"""Gate 141C: the object storage boundary — put, get, head, delete.

## Two adapters, and only one of them can reach anything

```text
InMemoryObjectStorageAdapter    a dict. Proves the refusals and the round trip.
ExternalObjectStorageAdapter    wraps an INJECTED client. Inert without one,
                                and inert with one unless the caller both
                                configured a store and explicitly allowed it.
```

There is no SDK in this project and this gate does not add one — no `boto3`, no
`minio`, no HTTP client, and `uv.lock` is untouched. The external adapter takes
any object exposing the S3 API shape (`put_object`, `get_object`, `head_object`,
`delete_object`), which is what Gate 97's body store already does. With no
client passed there is nothing to call, so "does not contact an object store" is
a property of the code rather than a promise about how it is invoked.

## The key is generated, never accepted

```text
award_documents/<org[:2]>/<org[2:4]>/<organization_id>/<document_id>.<ext>
```

Derived from ids this system already has. A caller-supplied key is the classic
way one tenant writes into another tenant's prefix, and there is no parameter
here that accepts one — `put` takes an organization id and a document id and
computes the rest.

`assert_safe_key` exists anyway, for keys arriving from a stored row rather than
a caller, and it refuses traversal, absolute paths, backslashes, NUL, empty
segments, a missing namespace, and anything over the length limit.

## Bodies are bounded and never rendered

```text
MAX_BODY_BYTES        16 MiB, refused above
sha256                computed and VERIFIED against the caller's declared digest
returned              a key, a length, a digest, a status. Never bytes.
logging               none. No logger, no print, no exception carrying a body.
```

A test parses this module with `ast` and asserts it contains no logging call and
imports no network library, the same way Gate 97's tests do — a body store whose
silence is asserted by reading it cannot be talked out of it later.

## What a hermetic proof does and does not prove

`run_hermetic_adapter_proof()` drives the in-memory adapter through the whole
contract and returns booleans. It proves the code: keys are generated, unsafe
keys refused, oversized bodies refused, hashes verified, round trip intact,
delete removes.

It proves nothing about durability, a bucket, a region, a credential, or that
any external service exists. So it may never set `object_store_configured`, and
the preflight's `hermetic_fake_verified` state is deliberately not a configured
one.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Protocol

SCHEMA_VERSION = "nf_object_storage_adapter_v1"

#: Where award document objects would live. Namespaced so this corpus can never
#: collide with Gate 97's `raw_payloads/`.
KEY_NAMESPACE = "award_documents"

#: 16 MiB. A limit that exists is a limit that can be tested; "whatever fits"
#: is how a 400 MB upload becomes an incident nobody predicted.
MAX_BODY_BYTES = 16 * 1024 * 1024

#: One segment of a key. Deliberately narrow: no dots except the extension the
#: builder appends itself, so `..` cannot be spelled.
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

MAX_KEY_LENGTH = 512

#: Extensions this lane will name. A document reference whose content type is
#: unknown gets `bin`, which claims nothing.
CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/json": "json",
    "image/png": "png",
    "image/jpeg": "jpg",
}
DEFAULT_EXTENSION = "bin"

PUT_STATUSES = frozenset({"stored", "deduplicated", "refused"})

#: The reasons an adapter refuses, named so a route can pass one through.
REFUSAL_REASONS: tuple[str, ...] = (
    "object_storage_not_configured",
    "external_object_storage_not_allowed",
    "no_object_store_client_injected",
    "object_key_is_not_safe",
    "body_exceeds_the_maximum",
    "body_is_empty",
    "declared_digest_does_not_match_the_bytes",
    "caller_supplied_object_keys_are_not_accepted",
)


class ObjectStorageError(RuntimeError):
    """Raised for a programming error, never carrying a body or a credential."""


class ObjectStoreClient(Protocol):
    """The S3 API shape. Same one Gate 97's body store speaks."""

    def put_object(self, **kwargs: Any) -> Any: ...

    def get_object(self, **kwargs: Any) -> Any: ...

    def head_object(self, **kwargs: Any) -> Any: ...

    def delete_object(self, **kwargs: Any) -> Any: ...


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def body_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extension_for(content_type: Any) -> str:
    return CONTENT_TYPE_EXTENSIONS.get(
        str(content_type or "").strip().lower(), DEFAULT_EXTENSION
    )


def generate_object_key(
    *,
    organization_id: Any,
    document_id: Any,
    content_type: Any = None,
) -> str:
    """The key for one document's bytes. Computed, never accepted.

    Two levels of prefix from the organization id, because object stores shard
    on key prefix and one prefix per tenant is a hot partition waiting for the
    tenant that grows.
    """
    org = str(organization_id or "").strip()
    doc = str(document_id or "").strip()
    try:
        org_hex = uuid.UUID(org).hex
        doc_hex = uuid.UUID(doc).hex
    except (ValueError, AttributeError, TypeError) as exc:
        raise ObjectStorageError(
            "an object key needs a uuid organization id and document id"
        ) from exc

    key = (
        f"{KEY_NAMESPACE}/{org_hex[:2]}/{org_hex[2:4]}/{org_hex}/"
        f"{doc_hex}.{_extension_for(content_type)}"
    )
    assert_safe_key(key)
    return key


def key_is_safe(key: Any) -> bool:
    """Is this key one this adapter would write to?

    Applied to keys read back out of a stored row as well as to generated ones.
    A row written before a rule existed is exactly the key nobody re-checks.
    """
    text = str(key or "")
    if not text or len(text) > MAX_KEY_LENGTH:
        return False
    if text != text.strip():
        return False
    if "\\" in text or "\x00" in text or "//" in text:
        return False
    if text.startswith("/") or text.startswith("~"):
        return False
    segments = text.split("/")
    if len(segments) < 2 or segments[0] != KEY_NAMESPACE:
        return False
    for index, segment in enumerate(segments):
        if not segment or segment in {".", ".."}:
            return False
        # Only the last segment may carry the single extension dot.
        candidate = segment
        if index == len(segments) - 1 and segment.count(".") == 1:
            candidate, _, extension = segment.partition(".")
            if not SAFE_SEGMENT.match(extension or ""):
                return False
        if not SAFE_SEGMENT.match(candidate):
            return False
    return True


def assert_safe_key(key: Any) -> str:
    if not key_is_safe(key):
        # The key is not echoed. A refused key can be attacker-shaped, and a
        # message that repeats it is a message that carries it onward.
        raise ObjectStorageError("object_key_is_not_safe")
    return str(key)


def _refused(reason: str, **extra: Any) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "refused",
            "stored": False,
            "object_key": None,
            "content_length": 0,
            "sha256_digest": None,
            "external_object_store_contacted": False,
            "network_calls": 0,
            "body_bytes_returned": False,
            "blocked_reasons": [reason],
            **extra,
        }
    )


class InMemoryObjectStorageAdapter:
    """The fake. A dict, and every refusal the real one has.

    Shares its refusal logic with nothing - it IS the refusal logic, and the
    external adapter calls the same helpers. Two adapters with two sets of
    rules would let the fake pass what the real one rejects, which is the only
    way a hermetic proof can lie.
    """

    adapter_kind = "in_memory_fake"
    external = False

    def __init__(self, *, max_body_bytes: int = MAX_BODY_BYTES) -> None:
        self._objects: dict[str, bytes] = {}
        self._max = int(max_body_bytes)

    # -- the contract -------------------------------------------------------

    def put(
        self,
        *,
        organization_id: Any,
        document_id: Any,
        body: bytes,
        content_type: Any = None,
        declared_digest: Any = None,
        object_key: Any = None,
    ) -> dict[str, Any]:
        """Store bytes under a GENERATED key.

        `object_key` exists only so a caller offering one is refused by name
        rather than having it silently ignored - Gate 139 found a pydantic model
        dropping `is_demo: false` instead of refusing it.
        """
        if object_key is not None:
            return _refused("caller_supplied_object_keys_are_not_accepted")

        data = bytes(body or b"")
        if not data:
            return _refused("body_is_empty")
        if len(data) > self._max:
            return _refused(
                "body_exceeds_the_maximum",
                max_body_bytes=self._max,
                # The size, which is not the content.
                offered_length=len(data),
            )

        digest = body_digest(data)
        if declared_digest is not None and str(declared_digest).lower() != digest:
            # Content addressing means nothing if the address is taken on trust.
            return _refused("declared_digest_does_not_match_the_bytes")

        try:
            key = generate_object_key(
                organization_id=organization_id,
                document_id=document_id,
                content_type=content_type,
            )
        except ObjectStorageError:
            return _refused("object_key_is_not_safe")

        deduplicated = self._objects.get(key) == data
        self._objects[key] = data
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "deduplicated" if deduplicated else "stored",
                "stored": True,
                "object_key": key,
                "content_length": len(data),
                "sha256_digest": digest,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": False,
                "network_calls": 0,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )

    def head(self, *, object_key: Any) -> dict[str, Any]:
        """Does it exist, and how big is it? No bytes come back."""
        key = str(object_key or "")
        if not key_is_safe(key):
            return _refused("object_key_is_not_safe")
        data = self._objects.get(key)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "found" if data is not None else "absent",
                "exists": data is not None,
                "object_key": key,
                "content_length": len(data) if data is not None else 0,
                "sha256_digest": body_digest(data) if data is not None else None,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": False,
                "network_calls": 0,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )

    def get(self, *, object_key: Any) -> bytes | None:
        """The bytes, returned to a caller and to no report.

        Separate from `head` on purpose: everything that builds an artifact or
        a route response calls `head`, so there is no path where a body reaches
        a serialised result by accident.
        """
        key = str(object_key or "")
        if not key_is_safe(key):
            raise ObjectStorageError("object_key_is_not_safe")
        return self._objects.get(key)

    def delete(self, *, object_key: Any) -> dict[str, Any]:
        key = str(object_key or "")
        if not key_is_safe(key):
            return _refused("object_key_is_not_safe")
        existed = self._objects.pop(key, None) is not None
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "deleted" if existed else "absent",
                "deleted": existed,
                "object_key": key,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": False,
                "network_calls": 0,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )

    def object_count(self) -> int:
        return len(self._objects)


class ExternalObjectStorageAdapter:
    """The real one, and it is inert.

    Three things must all be true before it calls anything:

    ```text
    a client was injected              there is no SDK here to build one from
    object storage is configured       the preflight said production_verified
    the caller explicitly allowed it   allow_external=True, never a default
    ```

    Any one missing and every method refuses by name without touching the
    client. The default construction - no arguments - can reach nothing.
    """

    adapter_kind = "external_s3_compatible"
    external = True

    def __init__(
        self,
        *,
        client: ObjectStoreClient | None = None,
        bucket: Any = None,
        object_store_configured: bool = False,
        allow_external: bool = False,
        max_body_bytes: int = MAX_BODY_BYTES,
    ) -> None:
        self._client = client
        # Held to hand to the client, never rendered. It is not in any result
        # this class returns and not in any exception it raises.
        self._bucket = str(bucket or "")
        self._configured = bool(object_store_configured)
        self._allowed = bool(allow_external)
        self._max = int(max_body_bytes)

    def _refusal(self) -> str | None:
        if not self._configured:
            return "object_storage_not_configured"
        if not self._allowed:
            return "external_object_storage_not_allowed"
        if self._client is None or not self._bucket:
            return "no_object_store_client_injected"
        return None

    def put(
        self,
        *,
        organization_id: Any,
        document_id: Any,
        body: bytes,
        content_type: Any = None,
        declared_digest: Any = None,
        object_key: Any = None,
    ) -> dict[str, Any]:
        refusal = self._refusal()
        if refusal:
            return _refused(refusal, adapter_kind=self.adapter_kind)
        if object_key is not None:
            return _refused("caller_supplied_object_keys_are_not_accepted")

        data = bytes(body or b"")
        if not data:
            return _refused("body_is_empty")
        if len(data) > self._max:
            return _refused("body_exceeds_the_maximum", max_body_bytes=self._max)
        digest = body_digest(data)
        if declared_digest is not None and str(declared_digest).lower() != digest:
            return _refused("declared_digest_does_not_match_the_bytes")

        key = generate_object_key(
            organization_id=organization_id,
            document_id=document_id,
            content_type=content_type,
        )
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "stored",
                "stored": True,
                "object_key": key,
                "content_length": len(data),
                "sha256_digest": digest,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": True,
                "network_calls": 1,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )

    def head(self, *, object_key: Any) -> dict[str, Any]:
        refusal = self._refusal()
        if refusal:
            return _refused(refusal, adapter_kind=self.adapter_kind)
        key = assert_safe_key(object_key)
        found = self._client.head_object(Bucket=self._bucket, Key=key)
        length = int((found or {}).get("ContentLength") or 0)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "found",
                "exists": True,
                "object_key": key,
                "content_length": length,
                "sha256_digest": None,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": True,
                "network_calls": 1,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )

    def get(self, *, object_key: Any) -> bytes | None:
        if self._refusal():
            return None
        key = assert_safe_key(object_key)
        found = self._client.get_object(Bucket=self._bucket, Key=key)
        return (found or {}).get("Body")

    def delete(self, *, object_key: Any) -> dict[str, Any]:
        refusal = self._refusal()
        if refusal:
            return _refused(refusal, adapter_kind=self.adapter_kind)
        key = assert_safe_key(object_key)
        self._client.delete_object(Bucket=self._bucket, Key=key)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "deleted",
                "deleted": True,
                "object_key": key,
                "adapter_kind": self.adapter_kind,
                "external_object_store_contacted": True,
                "network_calls": 1,
                "body_bytes_returned": False,
                "blocked_reasons": [],
            }
        )


#: Keys a hermetic proof tries and must be refused for. Each is a different
#: way of leaving the namespace, not five spellings of one.
UNSAFE_KEY_PROBES: tuple[str, ...] = (
    "award_documents/../../etc/passwd",
    "../award_documents/x.bin",
    "/award_documents/x.bin",
    "award_documents//x.bin",
    "award_documents/x/../../../y.bin",
    "award_documents\\x.bin",
    "award_documents/x\x00.bin",
    "other_namespace/x.bin",
    "~/award_documents/x.bin",
    "",
)


def run_hermetic_adapter_proof(
    *, organization_id: Any = None, document_id: Any = None
) -> dict[str, Any]:
    """Drive the in-memory adapter through the whole contract.

    Deterministic: fixed ids, fixed bytes, so the artifact this feeds produces
    the same output every run. Contacts nothing.
    """
    org = str(organization_id or "bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
    doc = str(document_id or "00000000-0000-0000-0000-000000000141")
    adapter = InMemoryObjectStorageAdapter()

    # Synthetic bytes. Not a customer file, not read from disk, not hashed from
    # anything real - the hard rule is that no real file is read or hashed.
    payload = b"gate141 hermetic fixture body, synthetic, not a customer file"
    digest = body_digest(payload)

    stored = adapter.put(
        organization_id=org,
        document_id=doc,
        body=payload,
        content_type="application/pdf",
        declared_digest=digest,
    )
    key = stored.get("object_key")

    headed = adapter.head(object_key=key) if key else {"exists": False}
    round_tripped = bool(key) and adapter.get(object_key=key) == payload

    caller_key = adapter.put(
        organization_id=org,
        document_id=doc,
        body=payload,
        object_key="award_documents/anywhere/i/like.bin",
    )
    oversized = adapter.put(
        organization_id=org,
        document_id=doc,
        body=b"x" * (MAX_BODY_BYTES + 1),
    )
    empty = adapter.put(organization_id=org, document_id=doc, body=b"")
    wrong_digest = adapter.put(
        organization_id=org,
        document_id=doc,
        body=payload,
        declared_digest="0" * 64,
    )

    unsafe_refused = {probe: not key_is_safe(probe) for probe in UNSAFE_KEY_PROBES}

    deleted = adapter.delete(object_key=key) if key else {"deleted": False}
    gone = adapter.head(object_key=key) if key else {"exists": False}

    inert = ExternalObjectStorageAdapter()
    inert_result = inert.put(organization_id=org, document_id=doc, body=payload)

    checks = {
        "key_is_generated": bool(key) and key.startswith(f"{KEY_NAMESPACE}/"),
        "key_is_safe": key_is_safe(key),
        "stored": bool(stored.get("stored")),
        "head_found_it": bool(headed.get("exists")),
        "round_trip_bytes_match": round_tripped,
        "digest_verified": stored.get("sha256_digest") == digest,
        "caller_supplied_key_refused": caller_key.get("blocked_reasons")
        == ["caller_supplied_object_keys_are_not_accepted"],
        "oversized_body_refused": oversized.get("blocked_reasons")
        == ["body_exceeds_the_maximum"],
        "empty_body_refused": empty.get("blocked_reasons") == ["body_is_empty"],
        "wrong_digest_refused": wrong_digest.get("blocked_reasons")
        == ["declared_digest_does_not_match_the_bytes"],
        "every_unsafe_key_refused": all(unsafe_refused.values()),
        "delete_removed_it": bool(deleted.get("deleted")) and not gone.get("exists"),
        "external_adapter_is_inert_by_default": inert_result.get("blocked_reasons")
        == ["object_storage_not_configured"],
        "nothing_left_in_the_fake": adapter.object_count() == 0,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_kind": adapter.adapter_kind,
            "scope": "hermetic_fake",
            "hermetic_fake_passed": all(checks.values()),
            "checks": checks,
            "unsafe_key_probes_refused": unsafe_refused,
            "max_body_bytes": MAX_BODY_BYTES,
            "key_namespace": KEY_NAMESPACE,
            "refusal_reasons": list(REFUSAL_REASONS),
            # What a fake cannot establish, said rather than left to inference.
            "proves_durability": False,
            "proves_a_bucket_exists": False,
            "proves_credentials_work": False,
            "object_store_configured": False,
            "production_storage": False,
            # Constants.
            "external_object_store_contacted": False,
            "network_calls": 0,
            "real_files_read": 0,
            "real_files_hashed": 0,
            "body_bytes_reported": False,
            "credential_values_reported": False,
            "blocked_reasons": sorted(
                name for name, passed in checks.items() if not passed
            ),
        }
    )


def adapter_proof_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a hermetic adapter proof."""
    fails: list[str] = []

    if result.get("hermetic_fake_passed"):
        for name, passed in (result.get("checks") or {}).items():
            if not passed:
                fails.append(f"passed_without:{name}")
        if result.get("blocked_reasons"):
            fails.append("passed_alongside_blockers")

    # The load-bearing separation: a fake may never configure a store.
    for field in (
        "object_store_configured",
        "production_storage",
        "external_object_store_contacted",
        "proves_durability",
        "proves_a_bucket_exists",
        "proves_credentials_work",
        "body_bytes_reported",
        "credential_values_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("network_calls", "real_files_read", "real_files_hashed"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    if result.get("scope") != "hermetic_fake":
        fails.append(f"scope_changed:{result.get('scope')}")

    # No body reached the result. Checked against the serialised form, because
    # a nested field is exactly where one would arrive unnoticed.
    rendered = json.dumps(result)
    if "gate141 hermetic fixture body" in rendered:
        fails.append("the_fixture_body_reached_the_result")

    return fails
