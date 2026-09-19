"""What a customer may be told about where an opportunity came from (164H).

A Tribal grants officer deciding whether to trust a listing needs to know
which authority published it, when it was retrieved, and that NativeForge did
not invent any of it. That is the whole customer-facing question.

What they must not receive is the machinery that answered it: who reviewed the
source, which warrant the request carried, what the database calls the row, or
anything about the machine that ran it.

## An allowlist, not a denylist

The fields are enumerated and the DTO is built from that list. A denylist
fails the moment a new internal field is added upstream - it would ship until
somebody noticed and added it to the list of things to hide. An allowlist
fails the other way: a new internal field is simply absent, and a new
customer-facing field has to be added deliberately.

`BLOCKED_FIELD_MARKERS` exists anyway, but as a NEGATIVE PROOF over the
serialized output rather than as the mechanism - two different jobs.

## Attribution is required, not optional

The Grants.gov terms carry `ATTRIBUTION_REQUIRED`. The notice is part of the
provenance payload, and `attribution_satisfied` is false when it is missing -
so a caller cannot render the opportunity and leave the notice out without
that being visible in the DTO it was handed.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_live_collection_customer_provenance_v1"

#: Everything a customer may see. Adding a field here is a deliberate act.
CUSTOMER_VISIBLE_FIELDS: tuple[str, ...] = (
    "source_name",
    "source_authority",
    "source_link",
    "retrieved_at",
    "source_opportunity_id",
    "opportunity_number",
    "opportunity_title",
    "agency_code",
    "open_date",
    "close_date",
    "attribution_notice",
    "attribution_satisfied",
    "normalized_from_source_evidence",
    "evidence_freshness",
)

#: Substrings that must not appear anywhere in the serialized DTO. Not the
#: mechanism - the allowlist is - but a check that the mechanism held.
BLOCKED_FIELD_MARKERS: tuple[str, ...] = (
    "reviewed_by",
    "reviewer",
    "review_authority",
    "warrant",
    "authorized_source_id",
    "guard_status",
    "decision_kind",
    "evidence_fingerprint",
    "payload_sha256",
    "attempt_id",
    "payload_id",
    "source_url_fingerprint",
    "request_fingerprint",
    "client_secret",
    "signing_key",
    "access_token",
    "database_url",
    "organization_id",
    "activation_approved_by",
    "activation_approval_artifact_id",
    "/home/",
    "/tmp/",
    ".env",
)

NOT_IMPLIED: tuple[str, ...] = (
    "provenance is not a recommendation or an eligibility opinion",
    "a retrieval time is not a freshness guarantee about the source",
    "nothing here is an authorization or a security statement",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_customer_provenance(
    *, audit: dict[str, Any] | None = None, retrieved_at: Any = None
) -> dict[str, Any]:
    """Build the customer-safe DTO from an audit view, by allowlist."""
    sections = (audit or {}).get("sections") or {}
    source = sections.get("source") or {}
    normalization = sections.get("normalization") or {}
    authorization = sections.get("authorization") or {}

    # The notice comes from the attribution service, never from a literal
    # retyped here - a retyped notice is one that can drift from the required
    # text while still looking right.
    notice = None
    try:
        from nativeforge.services.grants_gov_attribution_service import (
            ATTRIBUTION_TEXT,
        )

        notice = ATTRIBUTION_TEXT
    except Exception:  # noqa: BLE001
        notice = None

    terms = authorization.get("terms") or {}
    attribution_required = str(terms.get("guard_status") or "") == (
        "ATTRIBUTION_REQUIRED"
    )

    values: dict[str, Any] = {
        "source_name": source.get("source_name"),
        "source_authority": source.get("host"),
        "source_link": source.get("declared_endpoint"),
        "retrieved_at": retrieved_at,
        "source_opportunity_id": normalization.get("source_opportunity_id"),
        "opportunity_number": normalization.get("opportunity_number"),
        "opportunity_title": normalization.get("title"),
        "agency_code": normalization.get("agency_code"),
        "open_date": normalization.get("open_date"),
        "close_date": normalization.get("close_date"),
        "attribution_notice": notice,
        "attribution_satisfied": bool(notice) if attribution_required else None,
        "normalized_from_source_evidence": (
            "This listing was normalized from the source's own published "
            "response, retrieved directly from the authority named above. "
            "NativeForge did not author or alter the opportunity's content."
        ),
        "evidence_freshness": (
            "retrieved once, at the time shown" if retrieved_at else None
        ),
    }

    # Built FROM the allowlist, so an upstream field that is not on it cannot
    # arrive by accident.
    payload = {name: values.get(name) for name in CUSTOMER_VISIBLE_FIELDS}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provenance": payload,
            "customer_visible_fields": list(CUSTOMER_VISIBLE_FIELDS),
            "built_by": "allowlist",
            "attribution_required": attribution_required,
            "not_implied": list(NOT_IMPLIED),
        }
    )


def provenance_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a DTO that leaked an internal field or dropped the notice."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("built_by") != "allowlist":
        fails.append("the_dto_was_not_built_from_the_allowlist")

    payload = result.get("provenance") or {}
    extra = sorted(set(payload) - set(CUSTOMER_VISIBLE_FIELDS))
    if extra:
        fails.append(f"fields_outside_the_allowlist:{extra}")
    absent = sorted(set(CUSTOMER_VISIBLE_FIELDS) - set(payload))
    if absent:
        fails.append(f"allowlisted_fields_missing_from_the_dto:{absent}")

    # The negative proof, over the serialized form - a nested internal field
    # would not show up in a key check.
    serialized = json.dumps(result, default=str).lower()
    leaked = sorted(
        marker for marker in BLOCKED_FIELD_MARKERS if marker.lower() in serialized
    )
    if leaked:
        fails.append(f"internal_markers_in_the_customer_dto:{leaked}")

    if result.get("attribution_required") and not payload.get("attribution_notice"):
        fails.append("attribution_is_required_and_the_notice_is_absent")
    if (
        result.get("attribution_required")
        and payload.get("attribution_satisfied") is not True
    ):
        fails.append("attribution_is_required_and_not_marked_satisfied")

    return sorted(set(fails))
