"""NOFO/synopsis intelligence field-status contract (honest labels only)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_nofo_field_status_contract_v1"

STATUS_KNOWN = "known"
STATUS_EXTRACTED = "extracted"
STATUS_INFERRED = "inferred"
STATUS_MISSING = "missing"
STATUS_NEEDS_CONFIRMATION = "needs_confirmation"
STATUS_NOT_IN_SOURCE = "not_in_source"
STATUS_NOT_SUPPORTED = "not_supported"

ALLOWED_FIELD_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_KNOWN,
        STATUS_EXTRACTED,
        STATUS_INFERRED,
        STATUS_MISSING,
        STATUS_NEEDS_CONFIRMATION,
        STATUS_NOT_IN_SOURCE,
        STATUS_NOT_SUPPORTED,
    }
)

# Fields that must never be silently invented as known/extracted without evidence.
PROTECTED_FABRICATION_FIELDS: frozenset[str] = frozenset(
    {
        "proposal_narrative",
        "tribal_history",
        "community_statistics",
        "partnerships",
        "budget_amounts",
        "tribal_resolution_text",
        "certifications_signed",
        "past_performance",
        "pdf_nofo_full_text",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_field(
    *,
    value: Any,
    status: str,
    evidence_note: str = "",
    source_ref: str = "",
) -> dict[str, Any]:
    if status not in ALLOWED_FIELD_STATUSES:
        raise ValueError(f"invalid field status: {status!r}")
    return {
        "value": value,
        "status": status,
        "evidence_note": evidence_note,
        "source_ref": source_ref,
    }


def field_status_invariant_failures(field: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    status = str(field.get("status") or "")
    if status not in ALLOWED_FIELD_STATUSES:
        fails.append(f"bad_status:{status!r}")
    value = field.get("value")
    if status in {STATUS_MISSING, STATUS_NOT_IN_SOURCE, STATUS_NOT_SUPPORTED}:
        if value not in (None, "", [], {}):
            fails.append(f"nonempty_value_for_{status}")
    if status in {STATUS_KNOWN, STATUS_EXTRACTED} and (
        value is None or value == "" or value == []
    ):
        fails.append(f"empty_value_for_{status}")
    return fails


def assert_no_silent_fill(fields: dict[str, dict[str, Any]]) -> list[str]:
    """Fail if protected fabrication fields are marked known/extracted."""
    fails: list[str] = []
    for name, field in fields.items():
        if name in PROTECTED_FABRICATION_FIELDS:
            status = str(field.get("status") or "")
            if status in {STATUS_KNOWN, STATUS_EXTRACTED, STATUS_INFERRED}:
                fails.append(f"fabricated_or_overclaimed:{name}:{status}")
            if status != STATUS_NOT_SUPPORTED and name in {
                "proposal_narrative",
                "pdf_nofo_full_text",
            }:
                # These two must be explicitly not_supported in this block.
                if status not in {
                    STATUS_NOT_SUPPORTED,
                    STATUS_MISSING,
                    STATUS_NOT_IN_SOURCE,
                }:
                    fails.append(f"must_be_not_supported:{name}:{status}")
        fails.extend(field_status_invariant_failures(field))
    return fails


def build_field_status_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed_statuses": sorted(ALLOWED_FIELD_STATUSES),
            "protected_fabrication_fields": sorted(PROTECTED_FABRICATION_FIELDS),
            "nofo_pdf_extraction": "NOT_SUPPORTED",
            "proposal_drafting": "NOT_SUPPORTED",
            "live_ingest_claimed_default": False,
        }
    )
