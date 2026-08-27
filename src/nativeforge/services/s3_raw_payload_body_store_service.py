"""S3-compatible raw payload body store (Gate 97C).

Where response bodies live in production. It writes through an **injected
client** and imports no SDK, so the whole of its logic is exercised by tests
without a network, a credential or a vendor.

## No dependency, and that is the design

There is no ``boto3`` in this project and Gate 97 does not add one. The store
takes any object exposing ``put_object(Bucket=..., Key=..., Body=...)`` — the
S3 API shape that boto3, MinIO's SDK and every S3-compatible client already
speak. A caller in production passes a real client; a test passes a fake.

A body store whose refusal logic can only be tested by mocking around a network
call is a body store whose refusal logic is not tested. This one is.

## Content-addressed from the hash we already have

```text
raw_payloads/<hash[:2]>/<hash[2:4]>/<hash>.bin
```

Two levels of prefix because object stores shard on key prefix, and a million
objects under one prefix is a hot partition. The key is derived from
``response_body_hash`` — the same hash the metadata row carries — so a key and
its row cannot disagree about which bytes they mean.

## The hash is verified, not trusted

``store_body`` re-hashes the bytes it was handed and refuses if they do not
match the declared ``response_body_hash``. A caller that computed the hash from
different bytes than it passed is the exact failure that makes content
addressing meaningless, and it is cheap to catch here.

## Refuses by default, four ways

```text
allow_write=False              default: nothing is written
secret_scan_status != clean    a scanned-dirty body never reaches an object store
hash mismatch                  the bytes are not what the caller said
customer data                  needs its own explicit opt-in
```

Each is a separate switch because each is a different mistake, and one opt-in
should not grant another.

## Nothing is logged

No logger, no ``print``, no exception message carrying a body or a credential.
The service takes credentials only to hand them to a client it was given, and
never renders them. A test parses this module and asserts it contains no logging
call at all.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

SCHEMA_VERSION = "nf_s3_raw_payload_body_store_v1"

# Key prefix inside the bucket.
KEY_NAMESPACE = "raw_payloads"

BODY_STORE_STATUSES = frozenset(
    {"written", "refused", "dry_run", "already_present", "unconfigured"}
)

# Only `clean` permits a write. `pending` is not a pass.
SECRET_SCAN_SATISFYING = frozenset({"clean"})

HASH_HEX_LENGTH = 64

# Values that look like credentials and are not. AKIAIOSFODNN7EXAMPLE is AWS's
# own documentation key; treating it as real would mark a tutorial environment
# production-configured. Compared case-insensitively.
PLACEHOLDER_CREDENTIAL_VALUES = frozenset(
    {
        "akiaiosfodnn7example",
        "wjalrxutnfemi/k7mdeng/bpxrficyexamplekey",
        "changeme",
        "change-me",
        "changethis",
        "placeholder",
        "example",
        "test",
        "testing",
        "dummy",
        "fake",
        "none",
        "null",
        "todo",
        "your-access-key",
        "your-secret-key",
        "xxx",
        "xxxx",
        "secret",
        "minioadmin",
    }
)

# Substrings that mark a value as a placeholder wherever they appear.
PLACEHOLDER_SUBSTRINGS: tuple[str, ...] = (
    "example",
    "changeme",
    "change-me",
    "placeholder",
    "your-",
    "<",
    ">",
)


class ObjectStoreClient(Protocol):
    """The one method this store calls. boto3 and MinIO both satisfy it."""

    def put_object(self, **kwargs: Any) -> Any: ...


class BodyStoreError(RuntimeError):
    """Raised when a write is refused. Never carries a body or a credential."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def body_hash(data: bytes | str) -> str:
    payload = data.encode("utf-8") if isinstance(data, str) else bytes(data or b"")
    return hashlib.sha256(payload).hexdigest()


def is_placeholder_value(value: Any) -> bool:
    """Whether a setting value is a placeholder rather than configuration."""
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered in PLACEHOLDER_CREDENTIAL_VALUES:
        return True
    return any(marker in lowered for marker in PLACEHOLDER_SUBSTRINGS)


def object_key_for(response_body_hash: Any) -> str:
    """Content-addressed, sharded two levels so no prefix goes hot."""
    digest = str(response_body_hash or "")
    if len(digest) != HASH_HEX_LENGTH:
        raise BodyStoreError(
            "response_body_hash must be SHA-256 hex to derive an object key"
        )
    return f"{KEY_NAMESPACE}/{digest[:2]}/{digest[2:4]}/{digest}.bin"


def raw_payload_ref_for(*, bucket: Any, response_body_hash: Any) -> str:
    """The reference stored in nf_raw_source_payloads.raw_payload_ref."""
    return f"s3://{str(bucket or '')}/{object_key_for(response_body_hash)}"


def _refused(
    *, reasons: list[str], object_key: str | None = None
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "body_store_status": "refused",
            "object_key": object_key,
            "raw_payload_ref": None,
            "bytes_written": 0,
            "write_allowed": False,
            "blocked_reasons": sorted(set(reasons)),
            "client_invoked": False,
            "network_client_imported": False,
            "credential_rendered": False,
            "fabricated": False,
        }
    )


def store_body(
    *,
    body: bytes | str,
    response_body_hash: Any,
    bucket: Any,
    client: ObjectStoreClient | None = None,
    allow_write: bool = False,
    secret_scan_status: Any = None,
    contains_customer_data: bool = False,
    customer_data_allowed: bool = False,
    content_type: Any = None,
) -> dict[str, Any]:
    """Write one body through an injected client. Refuses by default."""
    reasons: list[str] = []

    # 1. Opt-in. A caller that forgot the argument writes nothing.
    if allow_write is not True:
        reasons.append("write_not_opted_in")

    # 2. A dirty body never reaches an object store.
    scan = str(secret_scan_status or "pending")
    if scan not in SECRET_SCAN_SATISFYING:
        reasons.append(f"secret_scan_not_clean:{scan}")

    # 3. Customer data needs its own opt-in.
    if contains_customer_data and customer_data_allowed is not True:
        reasons.append("customer_data_not_allowed")

    # 4. The bucket has to exist as configuration.
    if not str(bucket or "").strip():
        reasons.append("bucket_not_configured")

    # 5. The hash must be a hash, and must match the bytes.
    declared = str(response_body_hash or "")
    if len(declared) != HASH_HEX_LENGTH:
        reasons.append("response_body_hash_is_not_sha256_hex")
    else:
        actual = body_hash(body)
        if actual != declared:
            # Neither value is a secret, but neither is useful to a reader
            # either - what matters is that they disagreed.
            reasons.append("response_body_hash_does_not_match_body")

    # 6. Somewhere to write to.
    if client is None:
        reasons.append("no_object_store_client_supplied")

    if reasons:
        return _refused(reasons=reasons)

    key = object_key_for(declared)
    payload = body.encode("utf-8") if isinstance(body, str) else bytes(body)

    put_kwargs: dict[str, Any] = {"Bucket": str(bucket), "Key": key, "Body": payload}
    if content_type:
        put_kwargs["ContentType"] = str(content_type)

    try:
        client.put_object(**put_kwargs)  # type: ignore[union-attr]
    except Exception as exc:
        # The class name, not the message: a client's exception text can carry a
        # presigned URL or a header echo.
        return _refused(
            reasons=[f"object_store_write_failed:{type(exc).__name__}"],
            object_key=key,
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "body_store_status": "written",
            "object_key": key,
            "raw_payload_ref": raw_payload_ref_for(
                bucket=bucket, response_body_hash=declared
            ),
            "bytes_written": len(payload),
            "write_allowed": True,
            "blocked_reasons": [],
            "client_invoked": True,
            "network_client_imported": False,
            "credential_rendered": False,
            "response_body_hash": declared,
            "customer_data_stored": bool(contains_customer_data),
            "fabricated": False,
        }
    )


def build_client_config(*, settings: Any = None) -> dict[str, Any]:
    """Connection settings for a client, with the secret never rendered."""
    from nativeforge.lib.settings import get_settings

    st = settings or get_settings()

    endpoint = str(getattr(st, "raw_payload_object_store_endpoint", "") or "")
    bucket = str(getattr(st, "raw_payload_object_store_bucket", "") or "")
    region = str(getattr(st, "raw_payload_object_store_region", "") or "")
    access_key_id = str(
        getattr(st, "raw_payload_object_store_access_key_id", "") or ""
    )
    secret = getattr(st, "raw_payload_object_store_secret_access_key", None)
    # SecretStr renders `**********`; the value is only reachable through an
    # explicit get_secret_value(), which nothing here calls.
    secret_present = bool(
        str(getattr(secret, "get_secret_value", lambda: secret or "")()).strip()
    )

    fields = {
        "endpoint": endpoint,
        "bucket": bucket,
        "region": region,
        "access_key_id": access_key_id,
    }
    missing = [name for name, value in fields.items() if not value.strip()]
    if not secret_present:
        missing.append("secret_access_key")

    placeholders = [
        name
        for name, value in fields.items()
        if value.strip() and is_placeholder_value(value)
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "endpoint": endpoint,
            "bucket": bucket,
            "region": region,
            # Reported present or absent. The value is never rendered.
            "access_key_id_present": bool(access_key_id.strip()),
            "secret_access_key_present": secret_present,
            "credential_present": bool(access_key_id.strip() and secret_present),
            "force_path_style": bool(
                getattr(st, "raw_payload_object_store_force_path_style", False)
            ),
            "settings_missing": sorted(missing),
            "placeholder_settings": sorted(placeholders),
            "configured": not missing and not placeholders,
            "credential_rendered": False,
            "fabricated": False,
        }
    )


def body_store_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if result.get("credential_rendered") is not False:
        fails.append("result_claimed_to_render_a_credential")

    # Write results.
    if "body_store_status" in result:
        if result.get("body_store_status") not in BODY_STORE_STATUSES:
            fails.append("body_store_status_out_of_vocabulary")
        if result.get("network_client_imported") is not False:
            fails.append("body_store_imported_a_network_client")

        written = result.get("body_store_status") == "written"
        if written != bool(result.get("write_allowed")):
            fails.append("write_allowed_disagrees_with_status")
        if not written:
            if result.get("raw_payload_ref"):
                fails.append("refused_write_returned_a_payload_ref")
            if result.get("bytes_written"):
                fails.append("refused_write_reported_bytes")
            if not result.get("blocked_reasons"):
                fails.append("refusal_without_a_reason")
        else:
            if result.get("blocked_reasons"):
                fails.append("successful_write_with_blocked_reasons")
            if not result.get("raw_payload_ref"):
                fails.append("successful_write_without_a_payload_ref")
            # A ref must contain its own hash: that is what makes it content
            # addressed rather than a name.
            digest = str(result.get("response_body_hash") or "")
            if digest and digest not in str(result.get("raw_payload_ref") or ""):
                fails.append("payload_ref_is_not_content_addressed")

    # Client config results.
    if "configured" in result:
        for forbidden in ("secret_access_key", "access_key_id", "credential"):
            if forbidden in result:
                fails.append(f"config_rendered_a_credential_field:{forbidden}")
        if result.get("configured") and result.get("settings_missing"):
            fails.append("configured_with_missing_settings")
        if result.get("configured") and result.get("placeholder_settings"):
            fails.append("configured_with_placeholder_settings")

    return fails
