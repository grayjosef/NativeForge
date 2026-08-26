"""Opportunity identity and version keys (Gate 92E).

Federal grant data has **no single global identifier**, so identity is layered.
Each layer below exists because a naive scheme loses a record the layer above
it cannot see.

## L1 - opportunity identity

Primary key is the normalized ``opportunityNumber``: uppercase, whitespace and
hyphens stripped. It is the human-facing, cross-source-quotable key. The numeric
``opportunityId`` is stored alongside as a surrogate - it is stable and is the
required input to ``fetchOpportunity``, but agencies do not publish it, so
neither one alone is sufficient.

``opportunityTitle`` is **never** a key. It is 255 free-text characters an
agency may edit at will.

## The composite is mandatory

The key is ``(normalized_opportunity_number, doc_type)`` where ``doc_type`` is
``forecast`` or ``synopsis``. **A forecast and the synopsis it becomes share the
same opportunity number.** Keying on the number alone silently merges them and
destroys the forecasted -> posted transition - which is precisely the event a
Tribe that saw the forecast has been waiting for.

## L2 - versions are immutable rows

``(opportunity_id, doc_type, revision)``. A revision change writes a new row.
Nothing is ever updated in place, because the previous version is the evidence
that a change happened.

## L3 - cross-source joins

ALN is **many-to-many**. A single opportunity can carry several
(``alnist[]``/``alns[]``), so it is a relation, never a scalar column.

Agency identity spans three non-matching namespaces: Grants.gov
``agencyCode``/``topAgencyCode``, Federal Register ``agencies[].slug`` +
``parent_id``, and SAM's FPDS codes for Department/Agency with AAC codes for
Office. So this service declares that a crosswalk **table** is required and
refuses to match agencies by name string.

## L4 - fuzzy fallback, and why it is quarantined

Sources with no identifier at all (BIA news, HUD Exchange, DOE tables, NSPIRES)
get ``SHA-256(normalized_agency + normalized_title + earliest_deadline_date)``.
This is a *provisional* key. It carries ``is_provisional: True`` and must be
promoted to L1 the moment a real opportunity number appears in the text -
agency pages routinely announce an opportunity days before, or instead of, a
Grants.gov posting.

Nothing here fetches. These are key-construction rules over fields the research
pass documented.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_opportunity_identity_versioning_v1"

# Documented in the Grants.gov XML extract dictionary. A forecast and its
# resulting synopsis share an opportunity number, so doc_type is part of the key.
DOC_TYPES = frozenset({"forecast", "synopsis"})

IDENTITY_LAYERS = frozenset({"L1", "L2", "L3", "L4"})

# L4 keys are provisional by construction and may never be treated as L1.
PROVISIONAL_LAYERS = frozenset({"L4"})

# Fields that must never be used as a primary key, with the reason.
FORBIDDEN_KEY_FIELDS: dict[str, str] = {
    "opportunity_title": "255 free-text chars, freely edited by the agency",
    "agency_name": "three non-matching namespaces; use the crosswalk table",
    "citation": "page-based; can collide with corrections",
}

# ALN format, documented: NN.XXX - two digits, a period, three uppercase
# alphanumerics, no whitespace.
ALN_PATTERN = re.compile(r"^\d{2}\.[0-9A-Z]{3}$")

# The three agency namespaces the crosswalk must reconcile.
AGENCY_NAMESPACES = frozenset({"grants_gov", "federal_register", "sam_fpds_aac"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def normalize_opportunity_number(raw: Any) -> str:
    """Uppercase, strip whitespace and hyphens. Nothing else."""
    if raw is None:
        return ""
    return re.sub(r"[\s\-]+", "", str(raw)).upper()


def normalize_for_fuzzy_key(raw: Any) -> str:
    """Lowercase, collapse non-alphanumerics to single spaces, trim."""
    if raw is None:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(raw).lower()).strip()


def build_opportunity_identity(
    *,
    opportunity_number: Any,
    doc_type: Any,
    opportunity_id: Any = None,
    aln_list: list[Any] | None = None,
    agency_code: Any = None,
    top_agency_code: Any = None,
) -> dict[str, Any]:
    """L1 identity plus the L3 join keys that hang off it."""
    normalized = normalize_opportunity_number(opportunity_number)
    dt = str(doc_type).strip().lower() if doc_type is not None else ""

    alns = [str(a).strip().upper() for a in (aln_list or []) if str(a).strip()]
    # ALNs are validated, not corrected. A malformed one is reported as
    # malformed - guessing at the intended value is fabrication.
    aln_valid = [a for a in alns if ALN_PATTERN.match(a)]
    aln_malformed = [a for a in alns if not ALN_PATTERN.match(a)]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_layer": "L1",
            "normalized_opportunity_number": normalized,
            "doc_type": dt if dt in DOC_TYPES else "unknown",
            "composite_key": f"{normalized}|{dt}" if normalized and dt else "",
            "opportunity_id": opportunity_id,
            "opportunity_id_is_surrogate": True,
            "is_provisional": False,
            # L3, many-to-many by construction.
            "aln_list": aln_valid,
            "aln_malformed": aln_malformed,
            "aln_relation_is_many_to_many": True,
            "agency_code": agency_code,
            "top_agency_code": top_agency_code,
            "agency_crosswalk_required": True,
            "agency_matched_by_name": False,
            "fabricated": False,
        }
    )


def build_version_key(
    *,
    opportunity_id: Any,
    doc_type: Any,
    revision: Any,
    extract_version: Any = None,
) -> dict[str, Any]:
    """L2. A revision change is a new immutable row, never an in-place update."""
    dt = str(doc_type).strip().lower() if doc_type is not None else ""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_layer": "L2",
            "opportunity_id": opportunity_id,
            "doc_type": dt if dt in DOC_TYPES else "unknown",
            "revision": revision,
            # The extract's own Version field ("Forecast X" / "Synopsis X") is
            # kept for cross-checking, not for keying.
            "extract_version": extract_version,
            "version_key": f"{opportunity_id}|{dt}|{revision}",
            "is_immutable": True,
            "updates_in_place": False,
            "fabricated": False,
        }
    )


def build_fuzzy_fallback_key(
    *,
    agency: Any,
    title: Any,
    earliest_deadline_date: Any,
    source_id: Any = None,
) -> dict[str, Any]:
    """L4. Provisional only - promote to L1 when a real number appears."""
    parts = [
        normalize_for_fuzzy_key(agency),
        normalize_for_fuzzy_key(title),
        # The date is normalized only by trimming; no parsing, no inference.
        str(earliest_deadline_date).strip() if earliest_deadline_date else "",
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_layer": "L4",
            "fuzzy_key": digest,
            "key_inputs": parts,
            "source_id": source_id,
            "is_provisional": True,
            "must_promote_to_l1_when_number_found": True,
            # A near-match pass is a *candidate* generator. It never merges
            # records on its own.
            "near_match_rule": "normalized title similarity + deadline within 3 days",
            "near_match_auto_merges": False,
            "fabricated": False,
        }
    )


def identity_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    layer = record.get("identity_layer")
    if layer not in IDENTITY_LAYERS:
        fails.append("identity_layer_out_of_vocabulary")

    # A forbidden field must never appear as a key input at L1/L2.
    if layer in {"L1", "L2"}:
        for field in FORBIDDEN_KEY_FIELDS:
            if field in record:
                fails.append(f"forbidden_key_field_present:{field}")

    if layer == "L1":
        if not record.get("normalized_opportunity_number"):
            fails.append("l1_without_normalized_number")
        if record.get("doc_type") not in DOC_TYPES:
            fails.append("l1_doc_type_out_of_vocabulary")
        # The composite is mandatory - a key without doc_type merges a
        # forecast into its own synopsis.
        key = record.get("composite_key") or ""
        if "|" not in key:
            fails.append("l1_key_is_not_composite")
        elif key.split("|", 1)[1] not in DOC_TYPES:
            fails.append("l1_composite_key_missing_doc_type")
        if record.get("is_provisional") is not False:
            fails.append("l1_marked_provisional")
        if record.get("aln_relation_is_many_to_many") is not True:
            fails.append("aln_collapsed_to_scalar")
        if record.get("agency_crosswalk_required") is not True:
            fails.append("agency_crosswalk_not_required")
        if record.get("agency_matched_by_name") is not False:
            fails.append("agency_matched_by_name_string")
        for aln in record.get("aln_list") or []:
            if not ALN_PATTERN.match(str(aln)):
                fails.append(f"invalid_aln_in_valid_list:{aln}")

    if layer == "L2":
        if record.get("is_immutable") is not True:
            fails.append("version_row_not_immutable")
        if record.get("updates_in_place") is not False:
            fails.append("version_updates_in_place")
        if record.get("revision") is None:
            fails.append("version_key_without_revision")
        if record.get("doc_type") not in DOC_TYPES:
            fails.append("l2_doc_type_out_of_vocabulary")

    if layer == "L4":
        if record.get("is_provisional") is not True:
            fails.append("l4_not_marked_provisional")
        if record.get("must_promote_to_l1_when_number_found") is not True:
            fails.append("l4_promotion_rule_dropped")
        if record.get("near_match_auto_merges") is not False:
            fails.append("l4_near_match_auto_merges")
        if len(str(record.get("fuzzy_key") or "")) != 64:
            fails.append("l4_key_is_not_sha256")

    return fails
