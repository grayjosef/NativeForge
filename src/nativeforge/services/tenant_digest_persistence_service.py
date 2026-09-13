"""Gate 151D: persist a digest built by Gate 140, so an intent can re-read it.

## The normalized payload, not a rendering

What is stored is the digest as the builder produced it — items, counts,
caveats, suppressions — plus a sha256 over a canonical serialisation. The
renderer can re-render from that and check the hash, which proves a given
rendering came from this digest without the rendering being kept.

Storing the rendered body would put something email-shaped in a table, which is
how a preview-only lane quietly becomes a delivery lane.

## Nothing here decides what a digest says

The builder owns that. This service persists what it is handed and refuses what
it must not store. It does not recompute counts, re-derive caveats, or resolve
an UNKNOWN — a persistence layer that improved the thing it persisted would make
the stored record disagree with the one the tenant saw.

## The honesty fields are required, not optional

`items_human_review`, `items_with_unverified_deadlines` and
`items_with_unknown_reporting_burden` are stored whether or not they are zero.
A record that dropped them would let a digest look more certain after the fact
than it was at the time, which is the failure an audit of a missed deadline runs
into first.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.repositories.tenant_digest_records_repository import (
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
    archive_digest_record,
    get_digest_record,
    insert_digest_record,
    list_digest_records,
    payload_sha256,
)

SCHEMA_VERSION = "nf_tenant_digest_persistence_v1"

#: The scope in which a digest may be persisted today.
CONTROLLED_SCOPE = "controlled_dev_demo"

#: Fields the builder must supply for a digest to be persistable. Each is a
#: fact the record would otherwise lose.
REQUIRED_DIGEST_FIELDS: tuple[str, ...] = (
    "digest_id",
    "cadence",
    "items_total",
    "items_visible",
    "items_suppressed",
)

#: The honesty counts. Stored whether or not they are zero.
HONESTY_FIELDS: tuple[str, ...] = (
    "items_human_review",
    "items_with_unverified_deadlines",
    "items_with_unknown_reporting_burden",
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "email_delivery",
    "source_monitoring_live",
    "object_store_configured",
    "customer_auth_live",
    "verified_operational_binding",
    "controlled_customer_pilot",
    "production_rollout",
)

_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: Any) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def persist_digest(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest: dict[str, Any] | None = None,
    org_is_demo: bool | None = None,
    created_by_identity_id: Any = None,
    scope: str | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """Persist one digest, or say exactly why not.

    `persisted` is derived from the repository's own write, never asserted.
    """
    blocked: list[str] = []
    requested_scope = str(scope or CONTROLLED_SCOPE).strip().lower()
    normalized_org = str(organization_id or "").strip().lower()

    if requested_scope != CONTROLLED_SCOPE:
        blocked.append(f"scope_not_permitted:{requested_scope}")
    if normalized_org == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")

    if not isinstance(digest, dict) or not digest:
        blocked.append("no_digest_supplied")
        digest = {}

    missing = [
        name for name in REQUIRED_DIGEST_FIELDS if digest.get(name) is None
    ]
    blocked.extend(f"digest_missing_field:{name}" for name in missing)

    # A payload carrying an address or a subject is refused before it reaches
    # the repository, so the refusal names the shape rather than a column.
    leaked = _leaked_shapes(digest)
    blocked.extend(f"digest_payload_leaked:{name}" for name in leaked)

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": requested_scope,
                "organization_id": normalized_org or None,
                "digest_id": digest.get("digest_id"),
                "persisted": False,
                "rows_written": 0,
                "payload_sha256": None,
                "blocked_reasons": sorted(set(blocked)),
                "email_sent": False,
                "live_source_called": False,
                "object_store_contacted": False,
                "not_approved": list(NOT_APPROVED),
            }
        )

    result = insert_digest_record(
        connection=connection,
        organization_id=organization_id,
        digest=digest,
        org_is_demo=org_is_demo,
        created_by_identity_id=created_by_identity_id,
        **offered,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": requested_scope,
            "organization_id": normalized_org,
            "digest_id": digest.get("digest_id"),
            # Derived from the write, not asserted.
            "persisted": bool(result["rows_written"]),
            "rows_written": result["rows_written"],
            "payload_sha256": (result.get("record") or {}).get("payload_sha256"),
            "blocked_reasons": result["blocked_reasons"],
            "honesty_fields_stored": list(HONESTY_FIELDS),
            "rendered_body_stored": False,
            "recipient_stored": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
            "not_approved": list(NOT_APPROVED),
        }
    )


def read_digest(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_id: Any = None,
) -> dict[str, Any]:
    """Read a persisted digest back, and say whether its hash still checks."""
    result = get_digest_record(
        connection=connection,
        organization_id=organization_id,
        digest_id=digest_id,
    )
    record = result.get("record")

    hash_verified = False
    if record:
        hash_verified = record["payload_sha256"] == payload_sha256(
            record["digest_payload_json"]
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": result["organization_id"],
            "digest_id": result["digest_id"],
            "found": bool(record),
            "record": record,
            "payload_hash_verified": hash_verified,
            "blocked_reasons": result["blocked_reasons"],
        }
    )


def list_digests(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    result = list_digest_records(
        connection=connection,
        organization_id=organization_id,
        include_archived=include_archived,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": result["organization_id"],
            "count": len(result["records"]),
            "records": result["records"],
            "include_archived": include_archived,
            "blocked_reasons": result["blocked_reasons"],
        }
    )


def archive_digest(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_id: Any = None,
) -> dict[str, Any]:
    """Archive a digest. It stays readable by id; an audit needs it to."""
    result = archive_digest_record(
        connection=connection,
        organization_id=organization_id,
        digest_id=digest_id,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": result["organization_id"],
            "digest_id": result["digest_id"],
            "archived": result["archived"],
            "rows_written": result["rows_written"],
            "still_readable_by_id": True,
            "blocked_reasons": result["blocked_reasons"],
        }
    )


def verify_rendering(
    *,
    record: dict[str, Any] | None = None,
    rendered_from: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Did this rendering come from this stored digest?

    Compares a hash over the payload a renderer used against the one stored.
    Nothing is rendered here and no body is kept.
    """
    if not record:
        return {
            "schema_version": SCHEMA_VERSION,
            "verified": False,
            "blocked_reasons": ["no_record_supplied"],
        }

    stored = record.get("payload_sha256")
    recomputed = payload_sha256(
        rendered_from
        if rendered_from is not None
        else record.get("digest_payload_json")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "verified": bool(stored and stored == recomputed),
        "stored_sha256": stored,
        "recomputed_sha256": recomputed,
        "body_stored": False,
        "blocked_reasons": [] if stored == recomputed else ["payload_hash_mismatch"],
    }


def persistence_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a persistence result that claims more than it did."""
    fails: list[str] = []

    if result.get("persisted") and not result.get("rows_written"):
        fails.append("persisted_without_rows")
    if result.get("persisted") and result.get("blocked_reasons"):
        fails.append("persisted_alongside_blockers")
    if result.get("persisted") and not result.get("payload_sha256"):
        fails.append("persisted_without_a_payload_hash")

    if result.get("rendered_body_stored"):
        fails.append("a_rendered_body_was_stored")
    if result.get("recipient_stored"):
        fails.append("a_recipient_was_stored")

    for flag in ("email_sent", "live_source_called", "object_store_contacted"):
        if result.get(flag):
            fails.append(f"persistence_claimed_to_have:{flag}")

    if result.get("scope") and result["scope"] != CONTROLLED_SCOPE:
        if result.get("persisted"):
            fails.append("persisted_outside_the_controlled_scope")

    return sorted(set(fails))


#: Re-exported so the readiness service and the verifier name one demo org.
DEMO_ORGANIZATION = DEMO_ORGANIZATION_ID
